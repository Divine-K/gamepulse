import { API_ORIGIN } from '../../services/api'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { CodeBlock } from '../ui/CodeBlock'

const KEY = '$GAMEPULSE_KEY'

export function IntegrationPanel() {
  const base = `${API_ORIGIN}/api/v1/game`
  const steps = [
    {
      title: '1. Verify your key',
      text: 'Send a request with your key in the X-API-Key header. A 200 response returns your game.',
      code: `export GAMEPULSE_KEY="gp_xxxxxxxxxxxx_..."   # the key you copied

curl ${base}/me \\
  -H "X-API-Key: ${KEY}"`,
    },
    {
      title: '2. Register a player',
      text: 'Use your own player id as external_id. Calling this again for the same id returns the existing player, so it is safe to call on every login.',
      code: `curl -X POST ${base}/players \\
  -H "X-API-Key: ${KEY}" -H "Content-Type: application/json" \\
  -d '{"external_id": "player-42", "username": "Ada"}'`,
    },
    {
      title: '3. Start a session',
      text: 'The Idempotency-Key header makes retries safe: repeating the request returns the same session.',
      code: `curl -X POST ${base}/sessions \\
  -H "X-API-Key: ${KEY}" -H "Content-Type: application/json" \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -d '{"player_external_id": "player-42"}'`,
    },
    {
      title: '4. Send scores and end the session',
      text: 'Update the live score while playing, then end the session with the result. Achievements unlock automatically and are returned in the response.',
      code: `# live score (optional)
curl -X POST ${base}/scores \\
  -H "X-API-Key: ${KEY}" -H "Content-Type: application/json" \\
  -d '{"player_external_id": "player-42", "value": 1200, "session_id": "<session id>"}'

# end the session
curl -X POST ${base}/sessions/<session id>/end \\
  -H "X-API-Key: ${KEY}" -H "Content-Type: application/json" \\
  -d '{"score": 1500, "result": "win"}'`,
    },
    {
      title: '5. Send custom events',
      text: 'Track anything else with custom_ events. They show up in your Live Events feed and the event log.',
      code: `curl -X POST ${base}/events \\
  -H "X-API-Key: ${KEY}" -H "Content-Type: application/json" \\
  -d '{"event_type": "custom_boss_defeated", "player_external_id": "player-42", "payload": {"boss": "kraken"}}'`,
    },
  ]
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Connect your game"
          description="Five requests take you from a new key to live data on your dashboard."
        />
        <CardBody className="text-sm text-muted">
          Keep your API key on your game server where possible. A key shipped inside a client build
          can be extracted by players, so rotate it if you suspect it leaked.
        </CardBody>
      </Card>
      {steps.map((step) => (
        <Card key={step.title}>
          <CardHeader title={step.title} description={step.text} />
          <CardBody>
            <CodeBlock title="Shell" code={step.code} />
          </CardBody>
        </Card>
      ))}
    </div>
  )
}
