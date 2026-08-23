import {
  IAppAccessors, IConfigurationExtend, IHttp, ILogger, IModify, IPersistence, IRead,
} from '@rocket.chat/apps-engine/definition/accessors';
import { App } from '@rocket.chat/apps-engine/definition/App';
import { IMessage } from '@rocket.chat/apps-engine/definition/messages';
import { IAppInfo } from '@rocket.chat/apps-engine/definition/metadata';
import { IRoom } from '@rocket.chat/apps-engine/definition/rooms';
import { SettingType } from '@rocket.chat/apps-engine/definition/settings';
import { UIActionButtonContext } from '@rocket.chat/apps-engine/definition/ui';
import {
  BlockElementType, BlockType, IUIKitResponse, TextObjectType, UIKitActionButtonInteractionContext,
  UIKitViewSubmitInteractionContext,
} from '@rocket.chat/apps-engine/definition/uikit';
import {
  IActionsBlock, IButtonElement, IDividerBlock, IInputBlock, IPlainTextInputElement,
  ISectionBlock, IStaticSelectElement, ITextObject,
} from '@rocket.chat/apps-engine/definition/uikit/blocks';
import {
  IUIKitContextualBarViewParam, IUIKitModalViewParam,
} from '@rocket.chat/apps-engine/definition/uikit/UIKitInteractionResponder';
import { IUser } from '@rocket.chat/apps-engine/definition/users';
import { UserType } from '@rocket.chat/apps-engine/definition/users/UserType';
import { TaskCommand } from './commands/TaskCommand';
import { appUser, callBackend } from './lib/backend';

interface LaunchResult { url: string; expires_in: number; }
interface TaskResult { id: number; title: string; url: string; message: string; }

export class OpsTrackerApp extends App {
  public constructor(info: IAppInfo, logger: ILogger, accessors: IAppAccessors) { super(info, logger, accessors); }

  protected async extendConfiguration(configuration: IConfigurationExtend): Promise<void> {
    await configuration.settings.provideSetting({ id: 'backend_url', type: SettingType.STRING, packageValue: '', required: true, public: false, i18nLabel: 'backend_url_label', i18nDescription: 'backend_url_description' });
    await configuration.settings.provideSetting({ id: 'integration_secret', type: SettingType.PASSWORD, packageValue: '', required: true, public: false, i18nLabel: 'integration_secret_label', i18nDescription: 'integration_secret_description' });
    await configuration.slashCommands.provideSlashCommand(new TaskCommand(this));
    configuration.ui.registerButton({ actionId: 'create-task-from-message', labelI18n: 'message_action', context: UIActionButtonContext.MESSAGE_ACTION });
    configuration.ui.registerButton({ actionId: 'open-tasks-composer', labelI18n: 'composer_action', context: UIActionButtonContext.MESSAGE_BOX_ACTION });
    configuration.ui.registerButton({ actionId: 'open-tasks-room', labelI18n: 'room_action', context: UIActionButtonContext.ROOM_ACTION });
    configuration.ui.registerButton({ actionId: 'open-tasks-user', labelI18n: 'user_action', context: UIActionButtonContext.USER_DROPDOWN_ACTION });
  }

  public async executeActionButtonHandler(context: UIKitActionButtonInteractionContext, read: IRead, http: IHttp, _persistence: IPersistence, modify: IModify): Promise<IUIKitResponse> {
    const data = context.getInteractionData();
    if (data.actionId === 'create-task-from-message' && data.message) {
      const modal = await this.createTaskModal(data.message, data.user, read);
      return context.getInteractionResponder().openModalViewResponse(modal);
    }
    try {
      const launch = await this.launch(read, http, data.user, data.room, '/kanban');
      const view: IUIKitContextualBarViewParam = {
        title: { type: TextObjectType.PLAINTEXT, text: 'Задачи' },
        blocks: [
          { type: BlockType.SECTION, text: { type: TextObjectType.MARKDOWN, text: '**OpsTracker**\nМои задачи, общий список и Канбан.' } } as ISectionBlock,
          { type: BlockType.ACTIONS, elements: [{ type: BlockElementType.BUTTON, actionId: 'open-web', text: { type: TextObjectType.PLAINTEXT, text: 'Открыть задачи' }, url: launch.url } as IButtonElement] } as IActionsBlock,
          { type: BlockType.DIVIDER } as IDividerBlock,
          { type: BlockType.SECTION, text: { type: TextObjectType.MARKDOWN, text: 'Быстрое создание: `/task @alex Название priority:high due:tomorrow`' } } as ISectionBlock,
        ],
      };
      return context.getInteractionResponder().openContextualBarViewResponse(view);
    } catch (error) {
      await this.notify(data.user, data.room, `OpsTracker недоступен: ${error instanceof Error ? error.message : 'ошибка'}`, modify);
      return context.getInteractionResponder().successResponse();
    }
  }

  public async executeViewSubmitHandler(context: UIKitViewSubmitInteractionContext, read: IRead, http: IHttp, _persistence: IPersistence, modify: IModify): Promise<IUIKitResponse> {
    const data = context.getInteractionData();
    if (!data.view.id || !data.view.id.startsWith('opstracker-create-')) return context.getInteractionResponder().successResponse();
    const messageId = data.view.id.slice('opstracker-create-'.length);
    const message = await read.getMessageReader().getById(messageId);
    if (!message) return context.getInteractionResponder().viewErrorResponse({ viewId: data.view.id, errors: { title: 'Исходное сообщение больше недоступно' } });
    const state = data.view.state as Record<string, Record<string, string>>;
    const title = state.title?.title?.trim();
    if (!title) return context.getInteractionResponder().viewErrorResponse({ viewId: data.view.id, errors: { title: 'Введите название задачи' } });
    const assigneeId = state.assignee?.assignee?.trim();
    let assigneeUser: IUser | undefined;
    if (assigneeId) {
      try {
        assigneeUser = await read.getUserReader().getById(assigneeId);
      } catch (_error) {
        return context.getInteractionResponder().viewErrorResponse({ viewId: data.view.id, errors: { assignee: 'Выберите пользователя из списка' } });
      }
    }
    const due = state.due?.due?.trim();
    try {
      const response = await callBackend<TaskResult>(read, http, '/api/integrations/rocketchat/task-from-message', {
        user: appUser(data.user),
        source: this.messageSource(message),
        title,
        description: state.description?.description || '',
        assignee: assigneeUser ? appUser(assigneeUser) : null,
        assignee_username: assigneeUser?.username || null,
        priority: (state.priority?.priority || 'NORMAL').toUpperCase(),
        due_date: due ? `${due}T23:59:00Z` : null,
      });
      if (!response.ok) throw new Error(this.backendError(response.data));
      await this.notify(data.user, message.room, `✅ ${response.data.message}\n[${response.data.title}](${response.data.url})`, modify);
      return context.getInteractionResponder().successResponse();
    } catch (error) {
      return context.getInteractionResponder().viewErrorResponse({ viewId: data.view.id, errors: { title: error instanceof Error ? error.message : 'Не удалось создать задачу' } });
    }
  }

  private async createTaskModal(message: IMessage, currentUser: IUser, read: IRead): Promise<IUIKitModalViewParam> {
    const plain = (text: string): ITextObject => ({ type: TextObjectType.PLAINTEXT, text });
    let members: IUser[] = [];
    try {
      members = await read.getRoomReader().getMembers(message.room.id);
    } catch (_error) {
      members = [currentUser, message.sender];
    }
    const memberOptions = Array.from(new Map(
      [...members, currentUser]
        .filter((user) => (
          user.isEnabled
          && user.type === UserType.USER
          && !user.appId
          && !user.roles.includes('bot')
          && Boolean(user.username)
        ))
        .map((user) => [user.id, user]),
    ).values())
      .sort((a, b) => (a.name || a.username).localeCompare(b.name || b.username, 'ru'))
      .slice(0, 100)
      .map((user) => ({
        text: plain(user.name && user.name !== user.username ? `${user.name} (@${user.username})` : `@${user.username}`),
        value: user.id,
      }));
    return {
      id: `opstracker-create-${message.id}`,
      title: plain('Создать задачу'),
      submit: { type: BlockElementType.BUTTON, actionId: 'submit', text: plain('Создать') } as IButtonElement,
      close: { type: BlockElementType.BUTTON, actionId: 'close', text: plain('Отмена') } as IButtonElement,
      blocks: [
        { type: BlockType.INPUT, blockId: 'title', label: plain('Название'), element: { type: BlockElementType.PLAIN_TEXT_INPUT, actionId: 'title', placeholder: plain('Что нужно сделать?'), initialValue: (message.text || '').slice(0, 500) } as IPlainTextInputElement } as IInputBlock,
        { type: BlockType.INPUT, blockId: 'description', optional: true, label: plain('Описание'), element: { type: BlockElementType.PLAIN_TEXT_INPUT, actionId: 'description', placeholder: plain('Контекст и ожидаемый результат'), multiline: true } as IPlainTextInputElement } as IInputBlock,
        {
          type: BlockType.INPUT,
          blockId: 'assignee',
          optional: true,
          label: plain('Исполнитель'),
          element: {
            type: BlockElementType.STATIC_SELECT,
            actionId: 'assignee',
            placeholder: plain('Выберите исполнителя'),
            options: memberOptions,
          } as IStaticSelectElement,
        } as IInputBlock,
        {
          type: BlockType.INPUT,
          blockId: 'priority',
          label: plain('Приоритет'),
          element: {
            type: BlockElementType.STATIC_SELECT,
            actionId: 'priority',
            placeholder: plain('Выберите приоритет'),
            initialValue: 'NORMAL',
            options: [
              { text: plain('Низкий'), value: 'LOW' },
              { text: plain('Обычный'), value: 'NORMAL' },
              { text: plain('Высокий'), value: 'HIGH' },
              { text: plain('Критичный'), value: 'CRITICAL' },
            ],
          } as IStaticSelectElement,
        } as IInputBlock,
        { type: BlockType.INPUT, blockId: 'due', optional: true, label: plain('Срок (ГГГГ-ММ-ДД)'), element: { type: BlockElementType.PLAIN_TEXT_INPUT, actionId: 'due', placeholder: plain('2026-08-15') } as IPlainTextInputElement } as IInputBlock,
      ],
    };
  }

  private messageSource(message: IMessage) {
    const room = message.room;
    return {
      room_id: room.id,
      room_name: room.slugifiedName || room.displayName,
      room_type: room.type,
      message_id: message.id,
      thread_id: message.threadId,
      author_id: message.sender.id,
      author_username: message.sender.username,
      timestamp: message.createdAt?.toISOString() || new Date().toISOString(),
      text: (message.text || '').slice(0, 4000),
    };
  }

  private async launch(read: IRead, http: IHttp, user: IUser, room: IRoom | undefined, destination: string): Promise<LaunchResult> {
    const response = await callBackend<LaunchResult>(read, http, '/api/integrations/rocketchat/launch', {
      user: appUser(user), destination,
      room: room ? { room_id: room.id, room_name: room.slugifiedName || room.displayName, room_type: room.type } : null,
    });
    if (!response.ok) throw new Error(this.backendError(response.data));
    return response.data;
  }

  public backendError(data: unknown): string {
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === 'string') return detail;
      if (detail && typeof detail === 'object' && 'message' in detail) return String((detail as { message: unknown }).message);
    }
    return 'backend вернул ошибку';
  }

  public async notify(user: IUser, room: IRoom | undefined, text: string, modify: IModify): Promise<void> {
    if (!room) return;
    const builder = modify.getCreator().startMessage().setRoom(room).setText(text);
    await modify.getNotifier().notifyUser(user, builder.getMessage());
  }
}
