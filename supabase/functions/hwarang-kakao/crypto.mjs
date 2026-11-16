const encoder = new TextEncoder();
const hex = b => Array.from(new Uint8Array(b), v => v.toString(16).padStart(2, '0')).join('');
export const random = () => hex(crypto.getRandomValues(new Uint8Array(32)));
export const digest = async s => hex(await crypto.subtle.digest('SHA-256', encoder.encode(s)));
const bytes = s => Uint8Array.from(s.match(/../g), v => parseInt(v, 16));
async function key(secret, usage) {
  if (typeof secret !== 'string' || secret.length < 32) throw Error('Encryption key unavailable');
  const material = await crypto.subtle.importKey('raw', encoder.encode(secret), 'HKDF', false, ['deriveKey']);
  return crypto.subtle.deriveKey({name:'HKDF', hash:'SHA-256', salt:encoder.encode('hwarang-kakao-multi-v1'), info:encoder.encode('token-storage')}, material, {name:'AES-GCM',length:256}, false, [usage]);
}
export async function seal(value, secret, owner, generation) {
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const data=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:encoder.encode(`${owner}:${generation}`)},await key(secret,'encrypt'),encoder.encode(JSON.stringify(value)));
  return JSON.stringify({v:1,iv:hex(iv),ciphertext:hex(data)});
}
export async function unseal(raw,secret,owner,generation) {
  const obj=JSON.parse(raw);
  if(obj.v!==1||!/^[a-f0-9]{24}$/.test(obj.iv)||!/^[a-f0-9]{32,}$/.test(obj.ciphertext)||obj.ciphertext.length%2)throw Error('Invalid ciphertext');
  const value=await crypto.subtle.decrypt({name:'AES-GCM',iv:bytes(obj.iv),additionalData:encoder.encode(`${owner}:${generation}`)},await key(secret,'decrypt'),bytes(obj.ciphertext));
  return JSON.parse(new TextDecoder().decode(value));
}
