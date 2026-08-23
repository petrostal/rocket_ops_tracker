import { IHttp, IModify, IRead } from '@rocket.chat/apps-engine/definition/accessors';
import { ISlashCommand, SlashCommandContext } from '@rocket.chat/apps-engine/definition/slashcommands';
import { OpsTrackerApp } from '../OpsTrackerApp';
import { appUser, callBackend } from '../lib/backend';

interface TaskResult { id: number; title: string; url: string; message: string; }

export class TaskCommand implements ISlashCommand {
  public command = 'task';
  public i18nParamsExample = 'slash_params';
  public i18nDescription = 'slash_description';
  public providesPreview = false;

  public constructor(private readonly app: OpsTrackerApp) {}

  public async executor(context: SlashCommandContext, read: IRead, modify: IModify, http: IHttp): Promise<void> {
    const text = context.getArguments().join(' ').trim();
    const sender = context.getSender();
    const room = context.getRoom();
    if (!text) {
      await this.app.notify(sender, room, 'Использование: `/task [@user] название [priority:high] [due:2026-08-15]`', modify);
      return;
    }
    try {
      const response = await callBackend<TaskResult>(read, http, '/api/integrations/rocketchat/slash-command', {
        user: appUser(sender),
        room: { room_id: room.id, room_name: room.slugifiedName || room.displayName, room_type: room.type },
        command_text: text,
      });
      if (!response.ok) throw new Error(this.app.backendError(response.data));
      await this.app.notify(sender, room, `✅ ${response.data.message}\n[${response.data.title}](${response.data.url})`, modify);
    } catch (error) {
      await this.app.notify(sender, room, `Не удалось создать задачу: ${error instanceof Error ? error.message : 'неизвестная ошибка'}`, modify);
    }
  }
}

