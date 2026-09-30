import {C,esc,W,H,text,rect} from './charts.js';

let fontsPromise;
async function fonts(){
 if(!fontsPromise) fontsPromise=Promise.all(['Regular','Medium','SemiBold'].map(async (weight)=>{
  const r=await fetch(`assets/fonts/Prompt-${weight}.ttf`);if(!r.ok)throw Error('โหลดฟอนต์สำหรับส่งออกไม่สำเร็จ');
  const blob=await r.blob();const uri=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob);});
  return `@font-face{font-family:Prompt;src:url('${uri}') format('truetype');font-weight:${{Regular:400,Medium:500,SemiBold:600}[weight]}}`;
 })).then(v=>v.join(''));
 return fontsPromise;
}

export function saveBlob(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);}

function wrap(value,width,size){
 const ctx=document.createElement('canvas').getContext('2d');ctx.font=`${size}px Prompt`;
 const segments=typeof Intl.Segmenter==='function'?[...new Intl.Segmenter('th',{granularity:'word'}).segment(value)].map(s=>s.segment):Array.from(value);
 const result=[];let current='';for(const part of segments){if(current&&ctx.measureText(current+part).width>width){result.push(current.trim());current=part;}else current+=part;}if(current)result.push(current.trim());return result;
}

export async function exportChart({slide,view,state,source,index,format,theme}){
 await document.fonts.ready;const fontCss=await fonts();
 const filters=slide.controls.map(c=>`${c.label}: ${c.type==='checkbox'?(state[c.key]?'แสดง':'ซ่อน'):c.options.find(o=>o[0]===state[c.key])?.[1]}`).join(' · ');
 const top=146;const notes=wrap(view.note,W-84,15);const sourceLines=wrap(slide.foot+' · '+source,W-84,11);const filterLines=wrap(filters||'ภาพรวม',W-84,14);
 const bottom=top+H+20;const height=bottom+filterLines.length*24+notes.length*24+sourceLines.length*19+89;
 let head=text(42,39,'DM REMISSION  /  EVIDENCE TO POLICY',12,C.coral,'letter-spacing="1.5"')+text(W-42,39,`${String(index+1).padStart(2,'0')} / 14 · DRAFT`,12,C.muted,'text-anchor="end"');
 const titleLines=wrap(view.chartTitle,W-84,25);
 titleLines.forEach((t,i)=>head+=text(42,86+i*34,t,25,C.text,'font-weight="600"'));
 let y=bottom,foot='';filterLines.forEach(t=>{foot+=text(42,y,t,14,C.coral);y+=24;});y+=13;
 notes.forEach(t=>{foot+=text(42,y,t,15,C.muted);y+=24;});y+=14;
 sourceLines.forEach(t=>{foot+=text(42,y,t,11,C.faint);y+=19;});
 foot+=text(42,height-27,'ฉบับร่างเพื่อหารือ · ภาพตามการตั้งค่าที่เลือก · ข้อมูลสรุปจากเอกสารและตารางวิเคราะห์',10,C.faint);
 let markup=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${height}" viewBox="0 0 ${W} ${height}"><title>${esc(view.chartTitle)}</title><desc>${esc(view.summary+'. '+view.note)}</desc><defs><style>${fontCss}text{font-family:Prompt,sans-serif}</style></defs>${rect(0,0,W,height,C.bg)}${head}<g transform="translate(0 ${top})">${view.body}</g>${foot}</svg>`;
 if(theme==='light'){
  const colors={[C.bg]:'#ffffff',[C.text]:'#202a34',[C.muted]:'#4c5a67',[C.faint]:'#5d6a75',[C.grid]:'#e0e4e9',[C.coral]:'#bc4058',[C.soft]:'#ffe4e9',[C.mint]:'#267b65',[C.gold]:'#98631a',[C.purple]:'#7551aa',[C.neutral]:'#84929f',[C.panel]:'#f1f4f7'};
  markup=markup.replace(/#[0-9a-f]{6}/gi,c=>colors[c.toLowerCase()]||c);
 }
 const filename=`dmr-${String(index+1).padStart(2,'0')}-${slide.id}-${theme}`;
 const blob=new Blob([markup],{type:'image/svg+xml;charset=utf-8'});
 if(format==='svg'){saveBlob(blob,filename+'.svg');return;}
 const url=URL.createObjectURL(blob);
 try{const img=new Image();img.decoding='sync';await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(Error('สร้างภาพไม่สำเร็จ ลองดาวน์โหลด SVG'));img.src=url;});const canvas=document.createElement('canvas');const scale=2400/W;canvas.width=2400;canvas.height=Math.ceil(height*scale);const ctx=canvas.getContext('2d');ctx.scale(scale,scale);ctx.drawImage(img,0,0);const png=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!png)throw Error('สร้าง PNG ไม่สำเร็จ');saveBlob(png,filename+'.png');}finally{URL.revokeObjectURL(url);}
}
