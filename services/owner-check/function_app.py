"""Azure Functions host: authenticated webhook -> durable queue -> trusted App checks."""
import json
import os
import azure.functions as func
from azure.storage.queue import QueueClient
from scripts.owner_check_service import verify_webhook, handle, installation_api, scan

app = func.FunctionApp()

@app.route(route='github-owner-check', auth_level=func.AuthLevel.ANONYMOUS, methods=['POST'])
def webhook(req):
    try:
        body = req.get_body()
        payload = verify_webhook(body, req.headers.get('X-Hub-Signature-256'), os.environ['OWNER_WEBHOOK_SECRET'])
        event = req.headers.get('X-GitHub-Event', '')
        if event == 'ping':
            return func.HttpResponse('ok')
        if str(payload.get('installation', {}).get('id')) != os.environ['OWNER_APP_INSTALLATION_ID']:
            return func.HttpResponse(status_code=403)
        queue = QueueClient.from_connection_string(os.environ['AzureWebJobsStorage'], 'owner-check-events')
        # Queue is provisioned by the operator, never created through unauthenticated traffic.
        # Queue only routing identities, not untrusted PR bodies/diffs or large push payloads.
        minimal = {k: payload[k] for k in ('installation', 'repository', 'ref') if k in payload}
        if 'pull_request' in payload:
            minimal['pull_request'] = {'number': payload['pull_request']['number']}
        if 'repository' in minimal:
            repo = minimal['repository']
            minimal['repository'] = {'full_name': repo['full_name'], 'private': repo['private'], 'owner': {'id': repo['owner']['id']}}
        queue.send_message(json.dumps({'event': event, 'payload': minimal}))
        return func.HttpResponse(status_code=202)
    except Exception:
        return func.HttpResponse('Webhook rejected or queue unavailable', status_code=400)

@app.queue_trigger(arg_name='message', queue_name='owner-check-events', connection='AzureWebJobsStorage')
def process(message):
    task = json.loads(message.get_body())
    handle(task['payload'], task['event'], installation_api())

@app.timer_trigger(schedule='0 */5 * * * *', arg_name='timer', run_on_startup=False)
def reconcile(timer):
    scan(installation_api())
