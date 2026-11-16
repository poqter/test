import {makeWelcomeWorker} from './worker.mjs';
Deno.serve(makeWelcomeWorker((name: string)=>Deno.env.get(name)));
