import {makeTestWorker} from './worker.mjs';
Deno.serve(makeTestWorker((name: string)=>Deno.env.get(name)));
