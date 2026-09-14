# BuildApp — Log Structure Reference

| Field | Value |
|---|---|
| Owner | Product Management |
| Version | 0.1 |
| Related document | BuildApp — Logs and BI Infrastructure PRD |

**Note on language.** This document follows the writing rules of ASD-STE100: short sentences, active voice, and one idea per sentence, with technical nomenclature kept as-is.

## 1. Purpose

This document defines the shape of every log entry in BuildApp. It has three parts: the fields common to all logs, the rules for the session ID, and the full field list for each event that exists today.

## 2. Common Fields (Envelope)

Every log entry, for every event, must carry these fields. Event-specific fields sit inside the `properties` field, defined per event in Section 4.

| Field | Type | Required | Description |
|---|---|---|---|
| `event` | string | Yes | Fixed name of the event, for example `prompt_submitted`. |
| `event_version` | integer | Yes | Version of this event's field structure. Starts at 1 and goes up when fields change. |
| `timestamp` | string (ISO 8601, UTC) | Yes | Time the action happened, set by the component that saw it. |
| `user_id` | string | Yes | Enterprise ID of the user who caused the event. |
| `session_id` | string | No | ID of the session in progress at event time. See Section 3. (Not yet implemented.) |
| `project_id` | string | No | ID of the project in scope, set automatically on backend or provided by client. |
| `project_name` | string | No | Name of the project in scope, set automatically on backend or provided by client. |
| `source` | enum: `web_client`, `server` | Yes | Component that emitted the event. |
| `client_app_version` | string | No | Version of the BuildApp web app. Present only when `source` is `web_client`. |
| `properties` | object | Yes | Fields specific to this event. See Section 4. |

## 3. Session ID

A session is one continuous run of activity by one user. A session does not stop at a project boundary; a user can move between projects inside one session.

**The system starts a new session ID when:**

- The app loads and the user has no active session.
- An event arrives more than 30 minutes after the user's last event.
- An open session reaches a hard cap of 24 hours.
- The user logs out and back in.

**Rule for what counts as activity:** only user-initiated events extend a session — for example `prompt_submitted`, `code_edited_manually`, `publish_started`. System-driven events, such as `flapi_call_made` or an auto-refreshed `preview_loaded`, do not extend a session on their own.

**Test for classifying future events:** when the team adds a new event, apply this test, in order:

1. Does the event fire only as the direct result of one user action at that moment — a click, a keystroke, a submit, a drag? If yes, mark it active.
2. Could the event fire while the user is away from the screen — from a timer, a poll, a callback, or a retry? If yes, mark it passive, even if an earlier user action started the chain.
3. Is the event a receipt or a result of a prior request, rather than a new instruction from the user? If yes, mark it passive.

Every new event definition must carry a `session_activity` tag, set to `active` or `passive`. Engineering and Data must agree on the tag before the event ships. (Not yet captured in logs; implementation pending with session tracking.)

**Rule for multiple tabs:** the app must issue one shared, server-side session ID per user, not one session ID per open tab.

## 4. Event Log Structures

Each event below lists its trigger, a short description, and its `properties` fields. Common envelope fields from Section 2 are not repeated here.

### 4.1 Project Events

#### `project_created`
Trigger: the user creates a new project.

| Field | Type | Required | Description |
|---|---|---|---|
| `project_name` | string | Yes | Name the user gave the project. |

#### `project_opened`
Trigger: the user opens an existing project.

| Field | Type | Required | Description |
|---|---|---|---|
| `entry_point` | enum: `project_list`, `direct_link`, `auto_select` | Yes | How the project was opened: `project_list` for sidebar clicks, `direct_link` for URL navigation, `auto_select` for initial app load. |

#### `project_deleted`
Trigger: the user deletes a project.

### 4.2 Chat and Prompt Events

#### `prompt_submitted`
Trigger: the user sends an instruction to the model.

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt_id` | string (UUID) | Yes | Unique ID for this prompt. Other events reference it. |
| `prompt_length` | integer | Yes | Character count of the prompt. |
| `prompt_sequence_number` | integer | Yes | Position of this prompt within its project, starting at 1. If a part of another branch, the position in that tree. |
| `version_id` | string | Yes | The version ID the prompt was sent in. |


#### `response_received` || Not yet implemented
Trigger: the model returns a response to a prompt.

| Field | Type | Required | Description |
|---|---|---|---|
| `response_id` | string (UUID) | Yes | Unique ID for this response. Other events reference it. |
| `prompt_id` | string (UUID) | Yes | ID of the prompt this response answers. |
| `version_id` | string | Yes | The version ID the prompt was sent in. |
| `response_time_ms` | integer | Yes | Time from prompt send to response receipt. |
| `token_count_input` | integer | Yes | Token count of the model input. |
| `token_count_output` | integer | Yes | Token count of the model output. |
| `model_version` | string | Yes | Identifier of the model version that produced the response. |
| `generation_attempt` | integer | Yes | The number of attempts of regeneration for the current response. |

#### `response_regenerated` || Not yet implemented
Trigger: the user asks the model to try again on the same request.

| Field | Type | Required | Description |
|---|---|---|---|
| `prior_response_id` | string (UUID) | Yes | ID of the response being replaced. |
| `new_prompt_id` | string (UUID) | Yes | ID of the new prompt created by the regeneration action. |

#### `response_rated` || There is no rating system yet
Trigger: the user rates a response.

| Field | Type | Required | Description |
|---|---|---|---|
| `response_id` | string (UUID) | Yes | ID of the response being rated. |
| `rating_value` | enum: `up`, `down` | Yes | The rating the user gave. |
| `rating_comment_provided` | boolean | Yes | Whether the user also left a comment. |

### 4.3 Code Events

#### `code_generated`
Trigger: the model writes or changes code in response to a prompt.

| Field | Type | Required | Description |
|---|---|---|---|
| `response_id` | string (UUID) | Yes | ID of the response that produced this code. |
| `file_count` | integer | Yes | Number of files touched. |
| `line_count_added` | integer | Yes | Lines added, summed across files. |
| `line_count_removed` | integer | Yes | Lines removed, summed across files. |

#### `code_edited_manually`
Trigger: the user edits generated code by hand in the code view.

| Field | Type | Required | Description |
|---|---|---|---|
| `file_path` | string | Yes | Path of the file edited, relative to the project root. |
| `lines_changed` | integer | Yes | Lines added or removed by this edit. |

#### `file_created`
Trigger: a new file appears in the project, from the model or the user.

| Field | Type | Required | Description |
|---|---|---|---|
| `file_path` | string | Yes | Path of the new file. |
| `file_type` | string | Yes | File extension, for example `tsx` or `json`. |
| `created_by` | enum: `model`, `user` | Yes | Origin of the new file. |

#### `file_deleted`
Trigger: a file is removed from the project.

| Field | Type | Required | Description |
|---|---|---|---|
| `file_path` | string | Yes | Path of the deleted file. |
| `deleted_by` | enum: `model`, `user` | Yes | Origin of the delete action. |

### 4.4 Package and flapi Events

#### `data_source_added`
Trigger: the user adds a data source to the project.

| Field | Type | Required | Description |
|---|---|---|---|
| `data_source_type` | string | Yes | Type of data source, for now it is only `package`. |
| `data_source_id` | string | Yes | ID of the underlying data source. |

#### `data_source_removed`
Trigger: the user removes a data source from the project.

| Field | Type | Required | Description |
|---|---|---|---|
| `data_source_id` | string | Yes | ID of the data source. |
| `data_source_type` | string | Yes | Type of data source, for now it is only `package`. |

#### `flapi_call_made`
Trigger: the running app calls flapi.

| Field | Type | Required | Description |
|---|---|---|---|
| `data_source_id` | string | Yes | Package this call belongs to. |
| `endpoint` | string | Yes | flapi endpoint called. |
| `request_id` | string (UUID) | Yes | ID for tracing this call end to end. |
| `latency_ms` | integer | Yes | Time from request to response. |
| `status_code` | integer | Yes | HTTP status code of the response. |

#### `flapi_call_failed`
Trigger: a flapi call returns an error.

| Field | Type | Required | Description |
|---|---|---|---|
| `data_source_id` | string | Yes | Package this call belongs to. |
| `endpoint` | string | Yes | flapi endpoint called. |
| `request_id` | string (UUID) | Yes | ID matching the related `flapi_call_made` entry. |
| `error_code` | string | Yes | flapi error code. |
| `error_message` | string | No | Short, sanitized error text. |

### 4.5 Preview Events

#### `preview_loaded`
Trigger: the preview window renders.

| Field | Type | Required | Description |
|---|---|---|---|
| `load_time_ms` | integer | Yes | Time from trigger to a rendered preview. |
| `trigger` | enum: `manual_refresh`, `auto_on_code_change` | Yes | What caused the preview to load. |

#### `preview_error`
Trigger: the preview window fails to render.

| Field | Type | Required | Description |
|---|---|---|---|
| `error_type` | string | Yes | Category of the render failure. |
| `error_message` | string | No | Short, sanitized error text. |

#### `preview_interaction`
Trigger: the user interacts with the running preview, for example a click or a form entry.

| Field | Type | Required | Description |
|---|---|---|---|
| `interaction_type` | enum: `click`, `input`, `navigation` | Yes | Kind of interaction. |
| `element_id` | string | No | ID of the element interacted with, if the preview exposes one. |

### 4.6 Publish Events

#### `publish_started`
Trigger: the user starts the publish action.

#### `publish_succeeded`
Trigger: a publish action completes with success.

| Field | Type | Required | Description |
|---|---|---|---|
| `publish_duration_ms` | integer | Yes | Time from `publish_started` to success. |
| `published_url` | string | Yes | URL of the published app. |

#### `publish_failed`
Trigger: a publish action ends in failure.

| Field | Type | Required | Description |
|---|---|---|---|
| `error_type` | string | Yes | Category of the publish failure. |
| `publish_duration_ms` | integer | Yes | Time from `publish_started` to failure. |

#### `app_shared`
Trigger: a user shares the link to a published app.

| Field | Type | Required | Description |
|---|---|---|---|
| `share_method` | enum: `link_copy`, `email`, `other` | No | Method used to share the link. |

---