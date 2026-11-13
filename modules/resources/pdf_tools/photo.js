// Local-only document geometry. All points are normalized clockwise TL, TR, BR, BL.
export const fullCorners = () => [[0,0],[1,0],[1,1],[0,1]];
export function validCorners(points) {
  if (!Array.isArray(points) || points.length !== 4) return false;
  if (points.some(p=>p.length!==2 || p.some(v=>!Number.isFinite(v)||v<0||v>1))) return false;
  let area=0;
  for(let i=0;i<4;i++) {
    const a=points[i], b=points[(i+1)%4], c=points[(i+2)%4];
    if((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]) <= .0001) return false;
    area+=a[0]*b[1]-a[1]*b[0];
  }
  return area/2>.02;
}
function canvas(w,h) {const c=document.createElement('canvas');c.width=Math.max(1,Math.round(w));c.height=Math.max(1,Math.round(h));return c;}
// Find the largest connected light-paper region at bounded resolution, then
// fit its convex hull to four corners. Ambiguous/no-document scenes fall back
// to manual corners; no crop is ever applied by detection itself.
export function detectDocument(source) {
  const k=Math.min(1,480/Math.max(source.width,source.height));
  const c=canvas(source.width*k,source.height*k),ctx=c.getContext('2d',{willReadFrequently:true});
  ctx.drawImage(source,0,0,c.width,c.height);
  const {width:w,height:h}=c, data=ctx.getImageData(0,0,w,h).data;
  const gray=new Uint8Array(w*h),hist=new Uint32Array(256);
  for(let i=0;i<gray.length;i++){gray[i]=Math.round(.299*data[i*4]+.587*data[i*4+1]+.114*data[i*4+2]);hist[gray[i]]++;}
  let total=0,left=0,sum=0,best=-1,threshold=160;
  for(let i=0;i<256;i++)total+=i*hist[i];
  for(let i=0;i<255;i++){left+=hist[i];sum+=i*hist[i];if(!left||left===gray.length)continue;const score=left*(gray.length-left)*(sum/left-(total-sum)/(gray.length-left))**2;if(score>best){best=score;threshold=i;}}
  if(best<=0)return {points:fullCorners(),found:false};
  const visited=new Uint8Array(w*h),queue=new Int32Array(w*h);let largest=[];
  for(let start=0;start<gray.length;start++){
    if(visited[start]||gray[start]<=threshold)continue;
    let head=0,tail=1;queue[0]=start;visited[start]=1;const boundary=[];
    while(head<tail){const i=queue[head++],x=i%w,y=Math.floor(i/w);let edge=false;
      for(const [nx,ny] of [[x-1,y],[x+1,y],[x,y-1],[x,y+1]]){
        if(nx<0||nx>=w||ny<0||ny>=h){edge=true;continue;}
        const j=ny*w+nx;if(gray[j]<=threshold){edge=true;continue;}if(!visited[j]){visited[j]=1;queue[tail++]=j;}
      }
      if(edge)boundary.push([x,y]);
    }
    if(tail>(largest.area||0)){largest=boundary;largest.area=tail;}
  }
  if((largest.area||0)<w*h*.12||largest.area>w*h*.98)return {points:fullCorners(),found:false};
  const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  largest.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const lower=[],upper=[];
  for(const p of largest){while(lower.length>=2&&cross(lower.at(-2),lower.at(-1),p)<=0)lower.pop();lower.push(p);}
  for(const p of largest.toReversed()){while(upper.length>=2&&cross(upper.at(-2),upper.at(-1),p)<=0)upper.pop();upper.push(p);}
  let hull=lower.slice(0,-1).concat(upper.slice(0,-1));
  while(hull.length>4){let index=0,area=Infinity;for(let i=0;i<hull.length;i++){const a=Math.abs(cross(hull[(i+hull.length-1)%hull.length],hull[i],hull[(i+1)%hull.length]));if(a<area){area=a;index=i;}}hull.splice(index,1);}
  if(hull.length!==4)return {points:fullCorners(),found:false};
  let first=0;for(let i=1;i<4;i++)if(hull[i][0]+hull[i][1]<hull[first][0]+hull[first][1])first=i;
  hull=hull.slice(first).concat(hull.slice(0,first));
  const points=hull.map(([x,y])=>[x/(w-1),y/(h-1)]);
  return {points:validCorners(points)?points:fullCorners(),found:validCorners(points)};
}
export function warpDocument(source, edit, maxEdge=2600) {
  const pts=edit?.corners||fullCorners();
  if(!validCorners(pts))throw new Error('모서리가 교차하거나 문서 영역이 너무 작습니다. 네 모서리를 다시 맞춰 주세요.');
  const p=pts.map(([x,y])=>[x*(source.width-1),y*(source.height-1)]);
  const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
  let w=Math.max(dist(p[0],p[1]),dist(p[3],p[2])),h=Math.max(dist(p[0],p[3]),dist(p[1],p[2]));
  const scale=Math.min(1,maxEdge/Math.max(w,h));w=Math.max(2,Math.round(w*scale));h=Math.max(2,Math.round(h*scale));
  const [a,b,c,d]=p,dx1=b[0]-c[0],dx2=d[0]-c[0],dx3=a[0]-b[0]+c[0]-d[0],dy1=b[1]-c[1],dy2=d[1]-c[1],dy3=a[1]-b[1]+c[1]-d[1];
  const den=dx1*dy2-dx2*dy1;
  if(Math.abs(den)<1e-8)throw new Error('문서 영역을 계산할 수 없습니다.');
  const g=(dx3*dy2-dx2*dy3)/den,j=(dx1*dy3-dx3*dy1)/den;
  const A=b[0]-a[0]+g*b[0],B=d[0]-a[0]+j*d[0],D=b[1]-a[1]+g*b[1],E=d[1]-a[1]+j*d[1];
  const src=source.getContext('2d',{willReadFrequently:true}).getImageData(0,0,source.width,source.height).data;
  const out=canvas(w,h),ctx=out.getContext('2d'),im=ctx.createImageData(w,h),contrast=(100+Number(edit?.contrast||0))/100,brightness=Number(edit?.brightness||0)*2.55;
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const u=x/(w-1),v=y/(h-1),z=g*u+j*v+1;
    const sx=Math.max(0,Math.min(source.width-1,(A*u+B*v+a[0])/z)),sy=Math.max(0,Math.min(source.height-1,(D*u+E*v+a[1])/z));
    const x0=Math.floor(sx),y0=Math.floor(sy),x1=Math.min(source.width-1,x0+1),y1=Math.min(source.height-1,y0+1),fx=sx-x0,fy=sy-y0,offset=(y*w+x)*4;
    for(let n=0;n<3;n++){const value=(src[(y0*source.width+x0)*4+n]*(1-fx)+src[(y0*source.width+x1)*4+n]*fx)*(1-fy)+(src[(y1*source.width+x0)*4+n]*(1-fx)+src[(y1*source.width+x1)*4+n]*fx)*fy;im.data[offset+n]=(value-128)*contrast+128+brightness;}im.data[offset+3]=255;
  }
  ctx.putImageData(im,0,0);
  const angle=Number(edit?.angle||0)*Math.PI/180;if(!angle)return out;
  const rotated=canvas(w*Math.abs(Math.cos(angle))+h*Math.abs(Math.sin(angle)),h*Math.abs(Math.cos(angle))+w*Math.abs(Math.sin(angle))),rc=rotated.getContext('2d');
  rc.fillStyle='white';rc.fillRect(0,0,rotated.width,rotated.height);rc.translate(rotated.width/2,rotated.height/2);rc.rotate(angle);rc.drawImage(out,-w/2,-h/2);return rotated;
}
