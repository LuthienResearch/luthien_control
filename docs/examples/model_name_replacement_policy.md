# Model Name Replacement Policy

The `ModelNameReplacementPolicy` allows you to replace model names in requests based on a configured mapping. This is particularly useful when working with clients like Cursor that assume model strings matching known models must route through specific endpoints.

## Use Case

You want to use OpenAI API endpoints to access models from other providers like Gemini or Claude, but the client application (e.g., Cursor) assumes that certain model names must route through specific endpoints.

With this policy, clients can send requests with special model names that will be replaced with the actual model names before the request reaches the backend.

## Configuration Example

```json
{
  "type": "ModelNameReplacement",
  "model_mapping": {
    "fakename": "realname",
    "gemini-2.5-pro-preview-05-06": "gpt-4o",
    "claude-3-opus-20240229": "gpt-4-turbo"
  }
}
```

## Usage in a Serial Policy

```json
{
  "type": "SerialPolicy",
  "name": "my-policy",
  "components": [
    {
      "type": "ClientApiKeyAuth"
    },
    {
      "type": "ModelNameReplacement",
      "model_mapping": {
        "gemini-2.5-pro-preview-05-06": "gpt-4o"
      }
    },
    {
      "type": "AddApiKeyHeaderFromEnv",
      "api_key_env_var": "OPENAI_API_KEY"
    },
    {
      "type": "SendBackendRequest"
    }
  ]
}
```
