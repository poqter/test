import test from 'node:test';import assert from 'node:assert/strict';
import {forecastBase,parseWeather,fetchWeather,WEATHER_ENDPOINT} from '../supabase/functions/hwarang-kakao/weather.mjs';
const q={day:'2026-11-16',nx:62,ny:126,base_date:'20261116',base_time:'0500'};
function fixture(overrides={}) {const values={TMN:2,TMX:11,POP:20,SKY:3,PTY:0,...overrides};const rows=[];for(const [category,v] of Object.entries(values))for(const hour of (['POP','SKY','PTY'].includes(category)?Array.from({length:18},(_,i)=>i+6):[6]))rows.push({baseDate:q.base_date,baseTime:q.base_time,nx:q.nx,ny:q.ny,fcstDate:'20261116',fcstTime:String(hour).padStart(2,'0')+'00',category,fcstValue:String(v)});return {response:{header:{resultCode:'00'},body:{totalCount:rows.length,items:{item:rows}}}};}

test('official forecast selects publication only after ten minute latency including midnight',()=>{
 assert.deepEqual(forecastBase(new Date('2026-11-15T20:09:59Z')),{base_date:'20261116',base_time:'0200'});
 assert.deepEqual(forecastBase(new Date('2026-11-15T20:10:00Z')),{base_date:'20261116',base_time:'0500'});
 assert.deepEqual(forecastBase(new Date('2026-11-15T15:02:00Z')),{base_date:'20261115',base_time:'2300'});
});
test('official JSON parsed without raw provider strings',()=>{
 const result=parseWeather(fixture(),q);assert.equal(result.low,2);assert.equal(result.high,11);assert.equal(result.condition,'구름 많음');assert.equal(result.issued_time,'05:00');
});
test('wrong grid/base/day and truncated pages rejected',()=>{
 for(const field of ['nx','ny','baseDate','baseTime','fcstDate']){const f=fixture();f.response.body.items.item[0][field]='wrong';assert.throws(()=>parseWeather(f,q));}
 const f=fixture();f.response.body.totalCount=1001;assert.throws(()=>parseWeather(f,q));
});
test('missing daily low is unknown not invented from remaining hourly temperatures',()=>{const f=fixture();f.response.body.items.item=f.response.body.items.item.filter(r=>r.category!=='TMN');f.response.body.totalCount--;assert.equal(parseWeather(f,q).low,null);});
test('invalid codes or extreme values fail closed',()=>{for(const overrides of [{TMN:-999},{TMX:100},{POP:101},{SKY:2},{PTY:9}])assert.throws(()=>parseWeather(fixture(overrides),q));});
test('missing key never calls network; HTTP failure sanitized',async()=>{
 let calls=0;await assert.rejects(fetchWeather(async()=>{calls++;},'',q));assert.equal(calls,0);
 await assert.rejects(fetchWeather(async url=>{assert.equal(url.origin+url.pathname,WEATHER_ENDPOINT);return new Response('secret',{status:500});},'test',q),/Weather unavailable/);
});
test('bounded official fetch accepts JSON and rejects oversized body',async()=>{
 const result=await fetchWeather(async()=>Response.json(fixture()),'not-a-real-key',q);assert.equal(result.high,11);
 await assert.rejects(fetchWeather(async()=>new Response('x'.repeat(750001)),'not-a-real-key',q),/Weather too large/);
});
test('invalid real date, issue time, duplicate or partial hourly categories rejected',()=>{
 assert.throws(()=>parseWeather(fixture(),{...q,day:'2026-02-30'}));
 assert.throws(()=>parseWeather(fixture(),{...q,base_time:'2500'}));
 const partial=fixture();partial.response.body.items.item.find(r=>r.category==='SKY').fcstTime='1300';assert.throws(()=>parseWeather(partial,q));
 const duplicate=fixture();duplicate.response.body.items.item.push({...duplicate.response.body.items.item.find(r=>r.category==='POP')});duplicate.response.body.totalCount++;assert.throws(()=>parseWeather(duplicate,q));
});
