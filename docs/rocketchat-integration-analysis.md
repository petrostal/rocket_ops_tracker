# Rocket.Chat integration notes

OpsTracker uses documented Rocket.Chat extension surfaces:

- private Apps Engine message, composer, room and user actions;
- UIKit forms and contextual bars;
- a `/task` slash command;
- Rocket.Chat OAuth authorization-code login;
- server-side REST calls for identity synchronization and direct messages.

Apps Engine does not provide a stable arbitrary left-navigation item or a general external-iframe host. The private app therefore opens the full task UI in the browser and keeps compact interactions in UIKit.

Version-sensitive behavior is isolated:

- Apps Engine dependencies and permissions live in `rocketchat/app`;
- client permalink formatting lives in `backend/app/integrations/rocketchat/permalinks.py`;
- deployment endpoints and CSP origins come from configuration rather than package defaults.

Verify the supported Apps Engine API and client behavior against the Rocket.Chat version used by each deployment. Useful primary references:

- [Apps Engine](https://developer.rocket.chat/docs/rocketchat-apps-engine)
- [Action buttons](https://developer.rocket.chat/docs/action-buttons)
- [Contextual bar](https://developer.rocket.chat/docs/contextual-bar)
- [Third-party login](https://docs.rocket.chat/docs/third-party-login)
- [REST API](https://developer.rocket.chat/apidocs)
