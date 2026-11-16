import {makeHandler} from './handler.mjs';
import {makeWorker} from './worker.mjs';
const env=(name: string)=>Deno.env.get(name);
const account=makeHandler(env),worker=makeWorker(env);
Deno.serve((request: Request)=>new URL(request.url).pathname.endsWith('/tick')?worker(request):account(request));
