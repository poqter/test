import {fullCorners, validCorners, detectDocument, warpDocument} from "./photo.js";
import * as pdfjs from "./vendor/pdf.min.mjs";
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "./vendor/pdf.worker.min.mjs",
  import.meta.url,
).href;
const pdfOptions = {
  isEvalSupported: false,
  cMapUrl: new URL("./vendor/cmaps/", import.meta.url).href,
  cMapPacked: true,
  standardFontDataUrl: new URL("./vendor/standard_fonts/", import.meta.url)
    .href,
};
const { PDFDocument, degrees, PDFName, PDFRawStream, PDFNumber } = PDFLib;
const $ = (id) => document.getElementById(id),
  MB = 1000000;
const LIMIT = { files: 30, pages: 100, bytes: 200 * MB, pixels: 40_000_000 };
const colors = ["#4d78ac", "#d88741", "#578d7c", "#8c76ac", "#aa6880"];
let sources = new Map(),
  pages = [],
  undo = [],
  redo = [],
  outputs = [],
  zipBlob = null;
let busy = false,
  cancelled = false,
  revision = 0,
  renderVersion = 0,
  selectedOutput = 0,
  comparison = null,
  viewVersion = 0;
let marked = new Set(), lastMarked = null, dirtySent = null, downloadUrl = null;
const thumbs = new Map(),
  urls = new Set();
const message = (text = "") => ($("notice").textContent = text);
const size = (n) =>
  n < 1000000
    ? (n / 1000).toFixed(1) + " KB"
    : (n / 1000000).toFixed(2) + " MB";
const tick = () => new Promise((r) => setTimeout(r, 0));
const assertActive = () => {
  if (cancelled) throw new Error("작업을 취소했습니다.");
};
const safeName = (n) =>
  (n || "문서")
    .replace(/[\\/:*?"<>|\x00-\x1f]/g, "_")
    .replace(/\.pdf$/i, "")
    .replace(/[. ]+$/, "")
    .slice(0, 80) || "문서";
function el(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
function button(text, fn) {
  const b = el("button", text);
  b.onclick = fn;
  return b;
}
function post(type, extra = {}) {
  if (window.parent !== window)
    window.parent.postMessage(
      { isStreamlitMessage: true, type, ...extra },
      "*",
    );
}
post("streamlit:componentReady", { apiVersion: 1 });
let frameHeight = 0;
new ResizeObserver(() => {
  const h = Math.ceil(document.body.getBoundingClientRect().height) + 4;
  if (h !== frameHeight) {
    frameHeight = h;
    post("streamlit:setFrameHeight", { height: h });
  }
}).observe(document.body);
function syncDirty() {
  const dirty = pages.length > 0;
  if (dirty !== dirtySent) { dirtySent = dirty; post("streamlit:setComponentValue", {value: {hasWork: dirty}, dataType: "json"}); }
}
function invalidate() {
  syncDirty();
  revision++;
  clearResults();
  $("dirty").textContent =
    "다시 생성 필요 · 현재 편집 내용으로 결과를 만들어 주세요.";
}
function clearResults() {
  for (const x of outputs) x.viewer?.destroy();
  outputs = [];
  zipBlob = null;
  downloadUrl = null;
  $("downloadStatus").replaceChildren();
  for (const u of urls) URL.revokeObjectURL(u);
  urls.clear();
  $("results").replaceChildren();
  $("reviewPages").replaceChildren();
}
function commit(fn) {
  if (busy) return;
  undo.push(structuredClone(pages));
  if (undo.length > 40) undo.shift();
  redo = [];
  fn();
  invalidate();
  render();
}
function history(from, to) {
  if (busy || !from.length) return;
  to.push(structuredClone(pages));
  pages = from.pop();
  invalidate();
  render();
}
function settings() {
  const v = $("target").value;
  const target = v === "custom" ? Number($("custom").value) : Number(v);
  if (
    !Number.isFinite(target) ||
    target < 0 ||
    (v === "custom" && (target < 0.1 || target > 200))
  )
    throw new Error("목표 용량을 0.1~200MB 사이로 입력해 주세요.");
  return {
    mode: $("mode").value,
    name: safeName($("filename").value),
    target: Math.floor(target * MB),
    quality: $("quality").value,
    a4: $("size").value === "a4",
    raster: $("raster").checked,
    groupNames: $("useGroupNames").checked,
  };
}
function setBusy(value, label = "") {
  busy = value;
  $("editor").inert = value;
  $("review").inert = value;
  $("reset").disabled = value;
  $("busy").hidden = !value;
  $("progress").textContent = label;
  cancelled = false;
}
function progress(t) {
  $("progress").textContent = t;
  assertActive();
}
async function jpeg(canvas, quality) {
  const blob = await new Promise((resolve, reject) =>
    canvas.toBlob(
      (b) =>
        b ? resolve(b) : reject(new Error("이미지 압축에 실패했습니다.")),
      "image/jpeg",
      quality,
    ),
  );
  return new Uint8Array(await blob.arrayBuffer());
}
async function bitmap(blob) {
  const b = await createImageBitmap(blob, { imageOrientation: "from-image" });
  if (!b.width || b.width * b.height > LIMIT.pixels) {
    b.close();
    throw new Error("이미지는 한 장당 4,000만 화소 이하로 줄여 주세요.");
  }
  return b;
}
function canvasFor(w, h) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  return c;
}
async function imageCanvas(source, edge = 2600, rotation = 0) {
  const b = await bitmap(source.file);
  const turn = rotation % 180 !== 0;
  const w = turn ? b.height : b.width,
    h = turn ? b.width : b.height;
  const scale = Math.min(1, edge / Math.max(w, h));
  const c = canvasFor(w * scale, h * scale);
  const ctx = c.getContext("2d");
  ctx.fillStyle = "white";
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.translate(c.width / 2, c.height / 2);
  ctx.rotate((rotation * Math.PI) / 180);
  ctx.drawImage(
    b,
    (-b.width * scale) / 2,
    (-b.height * scale) / 2,
    b.width * scale,
    b.height * scale,
  );
  b.close();
  return c;
}
async function getViewer(source) {
  if (!source.viewer)
    source.viewer = await pdfjs.getDocument({
      data: source.bytes.slice(),
      ...pdfOptions,
    }).promise;
  return source.viewer;
}
async function renderPdf(viewer, index, edge, rotation = 0) {
  const p = await viewer.getPage(index + 1);
  const v = p.getViewport({ scale: 1, rotation: (p.rotate + rotation) % 360 });
  const scale = Math.min(edge / Math.max(v.width, v.height), 4);
  const vp = p.getViewport({ scale, rotation: (p.rotate + rotation) % 360 });
  const c = canvasFor(vp.width, vp.height);
  await p.render({
    canvasContext: c.getContext("2d"),
    viewport: vp,
    background: "white",
  }).promise;
  p.cleanup();
  return c;
}
async function editedImage(page, edge = 2600, rotation = 0) {
  const src = sources.get(page.source);
  if (!page.edit) return imageCanvas(src, edge, rotation);
  const raw = await imageCanvas(src, 4000);
  const corrected = warpDocument(raw, page.edit, Math.min(edge,4000));
  raw.width = raw.height = 1;
  if (!rotation) return corrected;
  const turn=rotation%180!==0,c=canvasFor(turn?corrected.height:corrected.width,turn?corrected.width:corrected.height),ctx=c.getContext("2d");
  ctx.translate(c.width/2,c.height/2);ctx.rotate(rotation*Math.PI/180);ctx.drawImage(corrected,-corrected.width/2,-corrected.height/2);corrected.width=corrected.height=1;return c;
}
async function pageCanvas(page, edge = 450, original = false) {
  const src = sources.get(page.source);
  if (src.type === "image") return original ? imageCanvas(src, edge, page.rotation) : editedImage(page, edge, page.rotation);
  return renderPdf(await getViewer(src), page.index, edge, page.rotation);
}
async function hash(bytes) {
  return Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
  )
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("");
}
async function addFiles(files) {
  if (busy) return;
  setBusy(true, "파일을 확인하고 있습니다…");
  $("errors").textContent = "";
  const failures = [];
  let changed = false;
  const before = structuredClone(pages);
  const oldIds = new Set(pages.map(p=>p.id));
  const anchors = pages.filter(p=>marked.has(p.id));
  const insertIndex = $("insertAt").value === "before" && anchors.length ? pages.indexOf(anchors[0]) : $("insertAt").value === "after" && anchors.length ? pages.indexOf(anchors.at(-1))+1 : pages.length;
  try {
    for (const file of files) {
      assertActive();
      let src = null;
      try {
        progress(file.name + " 확인 중…");
        if (sources.size >= LIMIT.files)
          throw new Error("파일은 최대 30개까지 추가할 수 있습니다.");
        if (
          [...sources.values()].reduce((n, s) => n + s.file.size, 0) +
            file.size >
          LIMIT.bytes
        )
          throw new Error("원본 전체 용량은 200MB 이하로 선택해 주세요.");
        if (!file.size) throw new Error("빈 파일입니다.");
        const bytes = new Uint8Array(await file.arrayBuffer());
        const digest = await hash(bytes);
        const duplicate = [...sources.values()].find(s => s.hash === digest && pages.some(p=>p.source===s.id));
        if (duplicate && !(await chooseDuplicate(file.name, duplicate.name))) continue;
        const id = crypto.randomUUID();
        src = {
          id,
          file,
          name: file.name,
          hash: digest,
          color: colors[sources.size % colors.length],
          type: /\.pdf$/i.test(file.name) ? "pdf" : "image",
          bytes,
        };
        let count = 1;
        if (src.type === "pdf") {
          let doc;
          try {
            doc = await PDFDocument.load(bytes);
          } catch (e) {
            throw new Error(
              /encrypt|password/i.test(String(e))
                ? "암호가 있는 PDF입니다. 첫 버전에서는 암호 해제된 사본을 사용해 주세요."
                : "PDF를 읽을 수 없습니다. 손상 여부를 확인해 주세요.",
            );
          }
          const form = doc.getForm();
          if (form.getFields().some((f) => f instanceof PDFLib.PDFSignature))
            throw new Error(
              "전자서명 필드가 있는 PDF는 이 도구에서 편집할 수 없습니다.",
            );
          if (form.getFields().length) {
            form.flatten();
            src.normalized = await doc.save();
          }
          count = doc.getPageCount();
          if (!count) throw new Error("페이지가 없는 PDF입니다.");
          src.doc = doc;
          const viewer = await getViewer(src);
          if (viewer.numPages !== count)
            throw new Error("PDF 페이지 구조를 확인할 수 없습니다.");
        } else {
          if (!/\.(png|jpe?g|webp|bmp)$/i.test(file.name))
            throw new Error("PDF·JPG·PNG·WEBP·BMP 파일만 지원합니다.");
          const c = await imageCanvas(src);
          src.width = c.width;
          src.height = c.height;
          src.embedType = "jpeg";
          if (file.size < MB && Math.max(c.width, c.height) < 2600) {
            const lossless = await new Promise((r) => c.toBlob(r, "image/png"));
            src.precompressed = new Uint8Array(await lossless.arrayBuffer());
            src.embedType = "png";
          } else src.precompressed = await jpeg(c, 0.9);
          c.width = c.height = 1;
          src.bytes = null;
        }
        if (pages.length + count > LIMIT.pages)
          throw new Error("전체 페이지는 최대 100쪽까지 추가할 수 있습니다.");
        sources.set(id, src);
        for (let i = 0; i < count; i++)
          pages.push({
            id: crypto.randomUUID(),
            source: id,
            index: i,
            rotation: 0,
            selected: true,
            split: false,
          });
        changed = true;
      } catch (e) {
        if (cancelled) throw e;
        if (src?.viewer) await src.viewer.destroy();
        failures.push(file.name + ": " + e.message);
      }
      await tick();
    }
  } catch (e) {
    message(e.message);
  } finally {
    setBusy(false);
    if (changed) {
      const added=pages.filter(p=>!oldIds.has(p.id));
      pages=pages.filter(p=>oldIds.has(p.id));pages.splice(insertIndex,0,...added);
      undo.push(before);
      redo = [];
      invalidate();
    }
    render();
    $("errors").textContent = failures.join("\n");
    $("files").value = "";
  }
}
async function chooseDuplicate(name, previous) {
  $("duplicateName").textContent=`${name} · 기존 파일: ${previous}`;
  const dialog=$("duplicateDialog");dialog.showModal();dialog.scrollIntoView({block:"center"});
  return new Promise(resolve=>{
    const done=value=>{dialog.close();resolve(value);};
    $("duplicateSkip").onclick=()=>done(false);$("duplicateKeep").onclick=()=>done(true);
    dialog.oncancel=e=>{e.preventDefault();done(false);};
  });
}
function moveMarked(beforeId=null, ids=marked) {
  if(beforeId && ids.has(beforeId))return;
  commit(()=>{const moving=pages.filter(p=>ids.has(p.id)),rest=pages.filter(p=>!ids.has(p.id));const at=beforeId?rest.findIndex(p=>p.id===beforeId):rest.length;rest.splice(at<0?rest.length:at,0,...moving);pages=rest;});
}
function selectionChanged() {
  marked=new Set([...marked].filter(id=>pages.some(p=>p.id===id)));
  $("batch").hidden=!marked.size;$("batchCount").textContent=`${marked.size}쪽 선택됨`;
  for(const card of $("pages").children){card.classList.toggle("marked",marked.has(card.dataset.id));card.querySelector('input[type=checkbox]').checked=marked.has(card.dataset.id);}
}
function move(id, delta) {
  const i = pages.findIndex((p) => p.id === id),
    j = i + delta;
  if (j < 0 || j >= pages.length) return;
  commit(() => {
    [pages[i], pages[j]] = [pages[j], pages[i]];
  });
}
function render() {
  const epoch = ++renderVersion;
  $("stepEdit").classList.add("active");
  $("stepReview").classList.remove("active");
  $("pages").replaceChildren();
  $("sources").replaceChildren();
  $("empty").hidden = pages.length > 0;
  $("count").textContent =
    `전체 ${pages.length}쪽 · 저장할 페이지 ${pages.filter((p) => p.selected).length}쪽`;
  $("generate").disabled = !pages.some((p) => p.selected);
  $("undo").disabled = !undo.length;
  $("redo").disabled = !redo.length;
  for (const src of sources.values()) {
    const own = pages.filter((p) => p.source === src.id);
    if (!own.length) continue;
    const div = el("div", undefined, "source");
    div.style.setProperty("--accent", src.color);
    const label = el("label");
    const cb = el("input");
    cb.type = "checkbox";
    cb.checked = own.every((p) => marked.has(p.id));
    cb.indeterminate = !cb.checked && own.some((p) => marked.has(p.id));
    cb.onchange = () => {own.forEach(p=>cb.checked?marked.add(p.id):marked.delete(p.id));render();};
    label.append(
      cb,
      document.createTextNode(src.name + " · " + own.length + "쪽"),
    );
    div.append(
      label,
      el(
        "small",
        src.type === "image"
          ? `원본 ${size(src.file.size)} → 준비 이미지 ${size(src.precompressed.length)}`
          : size(src.file.size),
      ),
    );
    const ids=new Set(own.map(p=>p.id));
    div.append(button("파일 맨 앞으로",()=>moveMarked(pages.find(p=>!ids.has(p.id))?.id,ids)),button("파일 맨 뒤로",()=>moveMarked(null,ids)),button("파일 제거",()=>{if(confirm(src.name+" 파일을 작업에서 제거할까요? 실행 취소할 수 있습니다."))commit(()=>{pages=pages.filter(p=>p.source!==src.id);});}));
    $("sources").append(div);
  }
  let ordinal = 0;
  const pending = [];
  for (const [index, page] of pages.entries()) {
    const src = sources.get(page.source);
    const card = el(
      "article",
      undefined,
      "card" + (page.selected ? "" : " off"),
    );
    card.dataset.id = page.id;
    card.draggable = true;
    card.style.setProperty("--accent", src.color);
    card.ondragstart = (e) => {
      e.dataTransfer.setData("text/plain", page.id);
      card.classList.add("dragging");
    };
    card.ondragend = () => card.classList.remove("dragging");
    card.ondragover = (e) => e.preventDefault();
    card.ondrop = (e) => {
      e.preventDefault();
      e.stopPropagation();
      const id = e.dataTransfer.getData("text/plain");
      if (id === page.id || !pages.some((p) => p.id === id)) return;
      moveMarked(page.id,marked.has(id)?marked:new Set([id]));
    };
    const head = el("div", undefined, "cardHead");
    const cb = el("input");
    cb.type = "checkbox";
    cb.checked = marked.has(page.id);
    cb.setAttribute(
      "aria-label",
      src.name + " " + (page.index + 1) + "쪽 선택",
    );
    cb.onclick = e => {
      if(e.shiftKey&&lastMarked){const a=pages.findIndex(p=>p.id===lastMarked),b=index;pages.slice(Math.min(a,b),Math.max(a,b)+1).forEach(p=>marked.add(p.id));}
      else cb.checked?marked.add(page.id):marked.delete(page.id);
      lastMarked=page.id;selectionChanged();
    };
    head.append(
      cb,
      el("span", page.selected ? `${++ordinal}페이지` : "제외됨"),
      el("b", "⠿", "handle"),
    );
    const thumb = el("div", undefined, "thumb");
    thumb.tabIndex = 0;
    thumb.setAttribute("role", "button");
    thumb.setAttribute("aria-label", "페이지 확대");
    thumb.onclick = () => showView(page);
    thumb.onkeydown = (e) => {
      if (e.key === "Enter") showView(page);
    };
    const img = el("img");
    img.alt = src.name + " 원본 " + (page.index + 1) + "쪽";
    thumb.append(img);
    const cacheKey = page.id + ":" + page.rotation + ":" + JSON.stringify(page.edit||null);
    if (thumbs.has(cacheKey)) img.src = thumbs.get(cacheKey);
    else pending.push({ img, page, key: cacheKey });
    const acts = el("div", undefined, "actions");
    const prev = button("←", () => move(page.id, -1));
    prev.title = "앞으로 이동";
    prev.disabled = index === 0;
    const next = button("→", () => move(page.id, 1));
    next.title = "뒤로 이동";
    next.disabled = index === pages.length - 1;
    acts.append(
      prev,
      next,
      button("↻ 회전", () =>
        commit(() => (page.rotation = (page.rotation + 90) % 360)),
      ),
      button("확대", () => showView(page)),
      button(page.selected?"저장에서 제외":"다시 포함",()=>commit(()=>page.selected=!page.selected)),
    );
    card.append(
      head,
      thumb,
      el("div", src.name + " · 원본 " + (page.index + 1) + "쪽", "caption"),
      acts,
    );
    if(page.groupName)card.append(el("div",page.groupName,"groupBadge"));
    if(src.type==="image")card.append(button(page.edit?"사진 보정 · 적용됨":"사진 보정",()=>openPhoto(page)));
    if ($("mode").value === "groups") {
      const split = button(
        page.split ? "✓ 여기서 나눔" : "＋ 여기서 나누기",
        () => commit(() => (page.split = !page.split)),
      );
      split.className = "split" + (page.split ? " on" : "");
      card.append(split);
    }
    $("pages").append(card);
  }
  selectionChanged();
  $("groupSummary").replaceChildren();
  const groupRows=groupsFor("groups");
  if(pages.some(p=>p.groupName||p.split))for(const [i,g] of groupRows.entries()){
    const row=el("div",undefined,"groupRow");row.append(el("strong",g[0].groupName||`그룹 ${i+1}`),el("span",`${g.length}쪽`));
    const rename=el("input");rename.value=g[0].groupName||"";rename.placeholder="그룹 이름";rename.setAttribute("aria-label",`그룹 ${i+1} 이름`);rename.maxLength=50;
    rename.onchange=()=>commit(()=>g.forEach(p=>p.groupName=rename.value.trim()));row.append(rename);$("groupSummary").append(row);
  }
  (async () => {
    for (const job of pending) {
      if (epoch !== renderVersion) return;
      try {
        const c = await pageCanvas(job.page, 400);
        const data = c.toDataURL("image/jpeg", 0.8);
        c.width = c.height = 1;
        if (epoch !== renderVersion) return;
        thumbs.set(job.key, data);
        if (thumbs.size > 160) thumbs.delete(thumbs.keys().next().value);
        job.img.src = data;
      } catch {
        job.img.alt = "미리보기 실패 · 결과 생성 시 재확인";
      }
      await tick();
    }
  })();
}
function groupsFor(mode) {
  const groups = [];
  let group = [];
  for (const p of pages) {
    if (p.selected) {
      if ((mode === "groups" || mode === "size") && group.length && (p.groupId||"") !== (group.at(-1).groupId||"")) {groups.push(group);group=[];}
      if (mode === "pages") groups.push([p]);
      else group.push(p);
    }
    if ((mode === "groups" || mode === "size") && p.split && group.length) {
      groups.push(group);
      group = [];
    }
  }
  if (group.length) groups.push(group);
  return groups;
}
async function assemble(group, opt) {
  const out = await PDFDocument.create();
  for (const row of group) {
    assertActive();
    const src = sources.get(row.source);
    if (src.type === "pdf") {
      const [copy] = await out.copyPages(src.doc, [row.index]);
      copy.setRotation(
        degrees((copy.getRotation().angle + row.rotation) % 360),
      );
      out.addPage(copy);
    } else {
      let embedded;
      if (row.edit) {
        const c=await editedImage(row,opt.quality==="original"?4000:2600);
        if(opt.quality==="original"){const blob=await new Promise(r=>c.toBlob(r,"image/png"));embedded=await out.embedPng(await blob.arrayBuffer());}
        else embedded=await out.embedJpg(await jpeg(c,.92));
        c.width=c.height=1;
      } else if (opt.quality === "original") {
        const c = await imageCanvas(src, Infinity);
        const blob = await new Promise((r) => c.toBlob(r, "image/png"));
        embedded = await out.embedPng(await blob.arrayBuffer());
        c.width = c.height = 1;
      } else
        embedded =
          src.embedType === "png"
            ? await out.embedPng(src.precompressed)
            : await out.embedJpg(src.precompressed);
      const w = embedded.width,
        h = embedded.height;
      let pw, ph, margin;
      if (opt.a4) {
        [pw, ph] = w > h ? [842, 595] : [595, 842];
        margin = 22.7;
      } else {
        const k = 842 / Math.max(w, h);
        [pw, ph, margin] = [w * k, h * k, 0];
      }
      const p = out.addPage([pw, ph]);
      const k = Math.min((pw - 2 * margin) / w, (ph - 2 * margin) / h);
      p.drawImage(embedded, {
        x: (pw - w * k) / 2,
        y: (ph - h * k) / 2,
        width: w * k,
        height: h * k,
      });
      p.setRotation(degrees(row.rotation));
    }
    await tick();
  }
  return out.save();
}
// Recompress only uncomplicated RGB/gray JPEG XObjects. Leave masks, CMYK,
// custom Decode arrays and non-JPEG streams intact to avoid color/data corruption.
async function compressImages(bytes, edge, quality) {
  const doc = await PDFDocument.load(bytes);
  let count = 0;
  for (const [ref, obj] of doc.context.enumerateIndirectObjects()) {
    assertActive();
    if (!(obj instanceof PDFRawStream)) continue;
    const d = obj.dict;
    const val = (n) => String(d.get(PDFName.of(n)));
    const filter = d.get(PDFName.of("Filter"));
    const ascii85 =
      filter instanceof PDFLib.PDFArray &&
      filter.size() === 2 &&
      String(filter.get(0)) === "/ASCII85Decode" &&
      String(filter.get(1)) === "/DCTDecode";
    if (
      val("Subtype") !== "/Image" ||
      (val("Filter") !== "/DCTDecode" && !ascii85) ||
      !["/DeviceRGB", "/DeviceGray"].includes(val("ColorSpace")) ||
      ["SMask", "Mask", "Decode", "DecodeParms"].some((n) =>
        d.has(PDFName.of(n)),
      )
    )
      continue;
    let b;
    try {
      let raw = obj.contents;
      if (ascii85) {
        const wrapper = d.clone(doc.context);
        wrapper.set(PDFName.of("Filter"), PDFName.of("ASCII85Decode"));
        raw = PDFLib.decodePDFRawStream(
          PDFRawStream.of(wrapper, obj.contents),
        ).decode();
      }
      b = await createImageBitmap(new Blob([raw], { type: "image/jpeg" }));
      if (b.width * b.height > LIMIT.pixels) {
        b.close();
        continue;
      }
      const k = Math.min(1, edge / Math.max(b.width, b.height));
      const c = canvasFor(b.width * k, b.height * k);
      c.getContext("2d").drawImage(b, 0, 0, c.width, c.height);
      b.close();
      b = null;
      const encoded = await jpeg(c, quality);
      if (encoded.length < obj.contents.length) {
        const dict = d.clone(doc.context);
        dict.set(PDFName.of("Width"), PDFNumber.of(c.width));
        dict.set(PDFName.of("Height"), PDFNumber.of(c.height));
        dict.set(PDFName.of("BitsPerComponent"), PDFNumber.of(8));
        dict.set(PDFName.of("ColorSpace"), PDFName.of("DeviceRGB"));
        dict.set(PDFName.of("Filter"), PDFName.of("DCTDecode"));
        dict.set(PDFName.of("Length"), PDFNumber.of(encoded.length));
        doc.context.assign(ref, PDFRawStream.of(dict, encoded));
        count++;
      }
      c.width = c.height = 1;
    } catch (e) {
      b?.close();
      if (cancelled) throw e;
    }
    await tick();
  }
  return { bytes: await doc.save(), count };
}
async function rasterize(bytes, edge, quality) {
  const viewer = await pdfjs.getDocument({ data: bytes.slice(), ...pdfOptions })
    .promise;
  try {
    const doc = await PDFDocument.create();
    for (let i = 0; i < viewer.numPages; i++) {
      assertActive();
      const pg = await viewer.getPage(i + 1);
      const v = pg.getViewport({ scale: 1 });
      const c = await renderPdf(viewer, i, edge);
      const jpg = await jpeg(c, quality);
      const embedded = await doc.embedJpg(jpg);
      const p = doc.addPage([v.width, v.height]);
      p.drawImage(embedded, { x: 0, y: 0, width: v.width, height: v.height });
      c.width = c.height = 1;
      await tick();
    }
    return doc.save();
  } finally {
    await viewer.destroy();
  }
}
async function buildOutput(group,opt,label="") {
      const base = await assemble(group, opt);
      let best = base,
        raster = false,
        changed = 0;
      if (
        opt.target &&
        best.length > opt.target &&
        opt.quality !== "original"
      ) {
        for (const [edge, q] of [
          [2600, 0.86],
          [2000, 0.78],
          [1600, 0.68],
          [1200, 0.58],
        ]) {
          progress(
            `${label} 파일의 이미지 용량을 조절하고 있습니다…`,
          );
          const next = await compressImages(base, edge, q);
          if (next.bytes.length < best.length) {
            best = next.bytes;
            changed = next.count;
          }
          if (best.length <= opt.target) break;
        }
        if (best.length > opt.target && opt.raster) {
          for (const [edge, q] of [
            [2400, 0.85],
            [1800, 0.75],
            [1400, 0.65],
          ]) {
            progress(`${label} 파일을 이미지화하고 있습니다…`);
            const next = await rasterize(base, edge, q);
            if (next.length < best.length) {
              best = next;
              raster = true;
            }
            if (best.length <= opt.target) break;
          }
        }
      }

return {bytes:best,baseBytes:base.length,pages:structuredClone(group),target:opt.target,raster,changed};
}

async function generate() {
  if (busy) return;
  let opt;
  try {
    opt = settings();
  } catch (e) {
    message(e.message);
    return;
  }
  if(opt.mode==="size"&&!opt.target){message("용량별 분할은 목표 용량을 지정해 주세요.");return;}
  const groups = groupsFor(opt.mode);
  if (!groups.length) return;
  clearResults();
  setBusy(true, "PDF를 생성하고 있습니다…");
  $("errors").textContent = "";
  const prepared = [];
  let splitGroups = 0;
  let preparedZip = null;
  try {
    for (let i = 0; i < groups.length; i++) {
      progress(`${i + 1}/${groups.length} 파일 생성 중…`);
      const item = await buildOutput(groups[i],opt,`${i+1}/${groups.length}`);
      assertActive();
      prepared.push(item);
    }
    if(opt.mode==="size" && opt.target){
      const chunks=[];
      async function fit(item){
        assertActive();
        if(item.bytes.length<=opt.target||item.pages.length===1){chunks.push(item);return;}
        const middle=Math.ceil(item.pages.length/2);
        for(const part of [item.pages.slice(0,middle),item.pages.slice(middle)])await fit(await buildOutput(part,opt,"분할"));
      }
      for(const item of prepared){if(item.bytes.length>opt.target&&item.pages.length>1)splitGroups++;await fit(item);}
      // Combine complete groups/chunks only when the measured combined PDF fits.
      const packed=[];
      for(const chunk of chunks){
        const previous=packed.at(-1);
        if(previous && previous.bytes.length<=opt.target && chunk.bytes.length<=opt.target){
          const combined=await buildOutput([...previous.pages,...chunk.pages],opt,"묶음 확인");
          if(combined.bytes.length<=opt.target){packed[packed.length-1]=combined;continue;}
        }
        packed.push(chunk);
      }
      prepared.splice(0,prepared.length,...packed);
    }
    prepared.forEach((item,i)=>{
      const names=[...new Set(item.pages.map(p=>p.groupName).filter(Boolean))];
      const group=opt.groupNames&&names.length===1?"_"+safeName(names[0]):"";
      item.name=opt.name+group+(prepared.length>1?"_"+String(i+1).padStart(2,"0"):"")+".pdf";
    });
    if (prepared.length > 1) {
      progress("ZIP을 만들고 있습니다…");
      preparedZip = await makeZip(prepared);
      assertActive();
    }
    outputs = prepared;
    zipBlob = preparedZip;
    selectedOutput = 0;
    $("dirty").textContent = "";
    message(splitGroups ? `${splitGroups}개 묶음이 목표 용량을 넘어 페이지 단위로 나누었습니다. 최종 순서를 확인해 주세요.` : "");
    $("editor").hidden = true;
    $("review").hidden = false;
    $("stepEdit").classList.remove("active");
    $("stepReview").classList.add("active");
    await renderResults();
    window.scrollTo(0, 0);
  } catch (e) {
    clearResults();
    message(
      e.message ||
        "PDF 생성에 실패했습니다. 파일을 확인하고 다시 시도해 주세요.",
    );
  } finally {
    setBusy(false);
  }
}
async function makeZip(items) {
  const zip = new JSZip();
  for (const item of items) zip.file(item.name, item.bytes);
  return zip.generateAsync({ type: "blob", compression: "STORE" });
}
function validateNames() {
  const names = outputs.map((x) => x.name.toLocaleLowerCase());
  if (new Set(names).size !== names.length)
    throw new Error("파일명이 겹칩니다. 서로 다른 이름을 입력해 주세요.");
}
async function renameResult(index, value) {
  const old = outputs[index].name;
  outputs[index].name = safeName(value) + ".pdf";
  try {
    validateNames();
    if (outputs.length > 1) {
      setBusy(true, "변경된 파일명으로 ZIP을 준비합니다…");
      zipBlob = await makeZip(outputs);
    }
    message("");
    updateDownload();
  } catch (e) {
    outputs[index].name = old;
    message(e.message);
    $("results").querySelectorAll("input")[index].value = old;
  } finally {
    setBusy(false);
  }
}
function updateDownload() {
  $("zipSize").textContent = zipBlob
    ? `${outputs.length}개 PDF · ZIP 실제 용량 ${size(zipBlob.size)}`
    : outputs.length
      ? `PDF 실제 용량 ${size(outputs[0].bytes.length)}`
      : "";
  $("download").textContent = zipBlob ? "ZIP 다운로드" : "PDF 다운로드";
}
async function resultViewer(out) {
  if (!out.viewer)
    out.viewer = await pdfjs.getDocument({
      data: out.bytes.slice(),
      ...pdfOptions,
    }).promise;
  return out.viewer;
}
async function renderResults() {
  $("results").replaceChildren();
  const activeSources=[...new Set(outputs.flatMap(o=>o.pages.map(p=>p.source)))].map(id=>sources.get(id));
  const originals=activeSources.reduce((n,s)=>n+s.file.size,0),ready=activeSources.reduce((n,s)=>n+(s.precompressed?.length??s.file.size),0),final=outputs.reduce((n,o)=>n+o.bytes.length,0);
  $("sizeSummary").textContent=`사용한 원본 파일 ${size(originals)} → 자동 압축 후 준비 파일 ${size(ready)} → 최종 PDF 합계 ${size(final)}. 원본 용량은 파일 전체 기준이며, 페이지 제외·분할·보정에 따라 달라집니다.`;
  for (const [i, out] of outputs.entries()) {
    const row = el(
      "div",
      undefined,
      "result" + (selectedOutput === i ? " active" : ""),
    );
    const name = el("input");
    name.value = out.name;
    name.setAttribute("aria-label", `${i + 1}번 결과 파일명`);
    name.onchange = () => renameResult(i, name.value);
    const info = el("div");
    info.append(
      el("strong", `${out.pages.length}쪽 · ${size(out.bytes.length)}`),
      el("small", ` PDF 압축 전 ${size(out.baseBytes)} → 최종 ${size(out.bytes.length)}`, "subtle"),
    );
    const over = out.target && out.bytes.length > out.target;
    const badge = el(
      "span",
      out.target ? (over ? "목표 초과" : "목표 충족") : "제한 없음",
      "badge" + (over ? " warn" : ""),
    );
    const show = button("순서·화질 확인", async () => {
      selectedOutput = i;
      await renderResults();
    });
    row.append(name, info, badge, show, button("개별 PDF 다운로드",()=>download(i)));
    const groupNames=[...new Set(out.pages.map(p=>p.groupName||"미분류"))];
    info.append(el("small",groupNames.join(" · "),"subtle"));
    $("results").append(row);
    if (out.raster)
      $("results").append(
        el(
          "p",
          "이미지화된 PDF입니다. 글자 선택·검색이 제한되므로 화질을 확인해 주세요.",
          "subtle",
        ),
      );
    if (over) {
      const help=el("div",undefined,"overHelp");help.append(el("p",out.pages.length===1?"한 페이지가 목표 용량을 초과했습니다. 추가 압축 또는 목표 용량 변경이 필요합니다.":"목표 용량을 초과했습니다. 아래 방법을 선택하거나 현재 결과를 저장할 수 있습니다."));
      help.append(button("압축 설정 확인",()=>{backToEdit();$("quality").focus();}),button("용량별로 나누기",()=>{backToEdit();$("mode").value="size";invalidate();render();}),button("목표 용량 변경",()=>{backToEdit();$("target").focus();}));$("results").append(help);
    }
  }
  updateDownload();
  await renderReviewPages();
}
async function renderReviewPages() {
  const out = outputs[selectedOutput];
  if (!out) return;
  const epoch = ++renderVersion;
  $("reviewPages").replaceChildren();
  const viewer = await resultViewer(out);
  for (const [i, p] of out.pages.entries()) {
    if (epoch !== renderVersion) return;
    const src = sources.get(p.source);
    const card = el("article", undefined, "card");
    card.style.setProperty("--accent", src.color);
    const thumb = el("div", undefined, "thumb");
    const img = el("img");
    img.alt = `최종 ${i + 1}페이지`;
    thumb.append(img);
    thumb.onclick = () => showView(p, out, i);
    const acts = el("div", undefined, "actions");
    acts.append(button("화질 비교", () => showView(p, out, i)));
    card.append(
      el("div", `${i + 1}페이지`, "cardHead"),
      thumb,
      el("div", `${src.name} · 원본 ${p.index + 1}쪽`, "caption"),
      acts,
    );
    $("reviewPages").append(card);
    const c = await renderPdf(viewer, i, 450);
    if (epoch !== renderVersion) return;
    img.src = c.toDataURL("image/jpeg", 0.85);
    c.width = c.height = 1;
  }
}
async function showView(page, out = null, index = 0) {
  if (busy) return;
  comparison = { page, out, index };
  $("zoom").value = "1";
  $("viewTitle").textContent =
    sources.get(page.source).name + " · 원본 " + (page.index + 1) + "쪽";
  $("resultPane").hidden = !out;
  document.querySelector(".compare").classList.toggle("solo", !out);
  document.querySelector(".mobileTabs").hidden = !out;
  $("compareHint").hidden = !out;
  $("originalPane").classList.remove("mobileHide");
  $("resultPane").classList.add("mobileHide");
  refreshViewerTools();
  if(!$("viewer").open)$("viewer").showModal();
  $("viewer").scrollIntoView({ block: "center" });
  await drawComparison();
}
async function drawComparison() {
  const token = ++viewVersion;
  if (!comparison) return;
  const { page, out, index } = comparison;
  const zoom = Number($("zoom").value);
  try {
    const width = Math.max(
      250,
      Math.min(
        530,
        window.innerWidth < 650
          ? window.innerWidth - 65
          : window.innerWidth / 2 - 65,
      ),
    );
    const edge = Math.min(3600, width * 1.45 * zoom * 1.6);
    const a = await pageCanvas(page, edge, !!out);
    const b = out
      ? await renderPdf(await resultViewer(out), index, edge)
      : null;
    if (token !== viewVersion) {
      a.width = a.height = 1;
      if (b) b.width = b.height = 1;
      return;
    }
    for (const [c, id] of [
      [a, "originalCanvas"],
      [b, "resultCanvas"],
    ]) {
      if (!c) continue;
      const target = $(id);
      target.width = c.width;
      target.height = c.height;
      target.style.width = width * zoom + "px";
      target.style.height = "auto";
      target.getContext("2d").drawImage(c, 0, 0);
      c.width = c.height = 1;
    }
  } catch (e) {
    message("미리보기를 만들 수 없습니다: " + e.message);
  }
}
let sync = false;
const panes = [...document.querySelectorAll(".viewport")];
for (const [i, p] of panes.entries())
  p.onscroll = () => {
    if (sync) return;
    sync = true;
    const q = panes[1 - i];
    q.scrollLeft = p.scrollLeft;
    q.scrollTop = p.scrollTop;
    requestAnimationFrame(() => (sync = false));
  };
function download(index = null) {
  if (busy || !outputs.length) return;
  const item=Number.isInteger(index)?outputs[index]:null;
  const blob=item?new Blob([item.bytes],{type:"application/pdf"}):zipBlob||new Blob([outputs[0].bytes],{type:"application/pdf"});
  const name=item?item.name:zipBlob?safeName($("filename").value)+".zip":outputs[0].name;
  const url=URL.createObjectURL(blob);urls.add(url);
  const a=el("a","다시 다운로드");a.href=url;a.download=name;a.className="downloadAgain";
  $("downloadStatus").replaceChildren(el("span","다운로드를 요청했습니다. 파일이 보이지 않으면 다시 다운로드를 눌러 주세요. "),a);
  a.click();
}
function backToEdit(){ $("review").hidden=true;$("editor").hidden=false;render();window.scrollTo(0,0); }
$("files").onchange = (e) => addFiles([...e.target.files]);
$("drop").onkeydown = (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    $("files").click();
  }
};
$("drop").ondragover = (e) => {
  e.preventDefault();
  $("drop").classList.add("drag");
};
$("drop").ondragleave = () => $("drop").classList.remove("drag");
$("drop").ondrop = (e) => {
  e.preventDefault();
  $("drop").classList.remove("drag");
  addFiles([...e.dataTransfer.files]);
};
$("selectAll").onclick = () => {marked=new Set(pages.map(p=>p.id));render();};
$("excludeAll").onclick = () => {marked.clear();render();};
$("undo").onclick = () => history(undo, redo);
$("redo").onclick = () => history(redo, undo);
$("generate").onclick = generate;
$("cancel").onclick = () => {
  cancelled = true;
  $("progress").textContent = "현재 처리 후 취소합니다…";
};
$("back").onclick = backToEdit;
$("download").onclick = () => download();
for (const id of [
  "mode",
  "filename",
  "target",
  "custom",
  "quality",
  "size",
  "raster",
  "useGroupNames",
])
  $(id).addEventListener("change", () => {
    if (busy) return;
    invalidate();
    $("customWrap").hidden = $("target").value !== "custom";
    if (id === "mode") render();
  });
$("closeView").onclick = () => {
  $("viewer").close();
  comparison = null;
  viewVersion++;
};
$("viewer").addEventListener("close", () => {
  viewVersion++;
  comparison = null;
});
$("zoom").onchange = drawComparison;
$("tabOriginal").onclick = () => {
  $("originalPane").classList.remove("mobileHide");
  $("resultPane").classList.add("mobileHide");
};
$("tabResult").onclick = () => {
  $("resultPane").classList.remove("mobileHide");
  $("originalPane").classList.add("mobileHide");
};
$("reset").onclick = async () => {
  if (busy || !confirm("현재 파일과 편집 내용을 모두 비울까요?")) return;
  clearResults();
  for (const s of sources.values()) await s.viewer?.destroy();
  sources.clear();
  pages = [];
  undo = [];
  redo = [];
  thumbs.clear();
  marked.clear();syncDirty();
  $("review").hidden = true;
  $("editor").hidden = false;
  $("errors").textContent = "";
  $("dirty").textContent = "";
  message("");
  render();
};
window.addEventListener("beforeunload", (e) => {
  if (pages.length) {
    e.preventDefault();
    e.returnValue = "";
  }
});
$("selectRange").onclick=()=>{
  try{
    const chosen=new Set(),parts=$("range").value.replace(/[–—~]/g,"-").split(",");
    for(const part of parts){const m=part.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/);if(!m)throw Error();const a=Number(m[1]),b=Number(m[2]||m[1]);if(a<1||b<a||b>pages.length)throw Error();for(let i=a-1;i<b;i++)chosen.add(pages[i].id);}
    marked=chosen;render();message("");
  }catch{message("페이지 범위를 확인해 주세요. 예: 1–5, 8, 12");}
};
$("batchFront").onclick=()=>moveMarked(pages.find(p=>!marked.has(p.id))?.id);
$("batchBack").onclick=()=>moveMarked();
$("batchMove").onclick=()=>{const i=Number($("moveBefore").value)-1;if(!Number.isInteger(i)||!pages[i])return message("이동할 페이지 번호를 확인해 주세요.");moveMarked(pages[i].id);};
$("batchRotate").onclick=()=>commit(()=>pages.filter(p=>marked.has(p.id)).forEach(p=>p.rotation=(p.rotation+90)%360));
$("batchExclude").onclick=()=>commit(()=>pages.filter(p=>marked.has(p.id)).forEach(p=>p.selected=false));
$("batchInclude").onclick=()=>commit(()=>pages.filter(p=>marked.has(p.id)).forEach(p=>p.selected=true));
$("batchGroup").onclick=()=>{
  const name=$("groupName").value.trim();if(!name)return message("그룹 이름을 입력하거나 선택해 주세요.");
  commit(()=>{const selected=pages.filter(p=>marked.has(p.id)),first=pages.findIndex(p=>marked.has(p.id));if(!selected.length)return;const id=crypto.randomUUID();selected.forEach(p=>{p.groupId=id;p.groupName=name;p.split=false;});pages=pages.filter(p=>!marked.has(p.id));pages.splice(first,0,...selected);});
};
$("batchUngroup").onclick=()=>commit(()=>pages.filter(p=>marked.has(p.id)).forEach(p=>{delete p.groupId;delete p.groupName;p.split=false;}));
function refreshViewerTools(){
  if(!comparison)return;const {page,out,index}=comparison,list=out?out.pages:pages,position=out?index:list.findIndex(p=>p.id===page.id);
  $("viewPosition").textContent=`${position+1} / ${list.length}쪽`;
  $("viewPrev").disabled=position<=0;$("viewNext").disabled=position>=list.length-1;
  $("viewRotate").hidden=!!out;$("viewInclude").hidden=!!out;$("viewPhoto").hidden=!!out||sources.get(page.source).type!=="image";
  $("viewInclude").textContent=page.selected?"저장에서 제외":"다시 포함";
}
async function adjacentView(delta){if(!comparison)return;const {page,out,index}=comparison,list=out?out.pages:pages,i=(out?index:list.findIndex(p=>p.id===page.id))+delta;if(list[i])await showView(list[i],out,i);}
$("viewPrev").onclick=()=>adjacentView(-1);$("viewNext").onclick=()=>adjacentView(1);
$("viewRotate").onclick=async()=>{const p=comparison?.page;if(!p)return;commit(()=>p.rotation=(p.rotation+90)%360);await drawComparison();};
$("viewInclude").onclick=()=>{const p=comparison?.page;if(!p)return;commit(()=>p.selected=!p.selected);refreshViewerTools();};
$("viewPhoto").onclick=()=>{const p=comparison?.page;if(p)openPhoto(p);};
$("viewer").addEventListener("keydown",e=>{if(["INPUT","SELECT","TEXTAREA"].includes(e.target.tagName))return;if(e.key==="ArrowRight"){e.preventDefault();adjacentView(1);}if(e.key==="ArrowLeft"){e.preventDefault();adjacentView(-1);}});
let photoState=null,photoEpoch=0,dragCorner=-1,previewTimer=null;
async function openPhoto(page){
  if(busy)return;
  const epoch=++photoEpoch;
  $("photoStatus").textContent="사진을 준비하고 있습니다…";
  $("photoDialog").showModal();$("photoDialog").scrollIntoView({block:"center"});$("photoApply").disabled=true;
  try{
    const raw=await imageCanvas(sources.get(page.source),1800);
    if(epoch!==photoEpoch||!$("photoDialog").open){raw.width=raw.height=1;return;}
    photoState={page,raw,edit:structuredClone(page.edit||{corners:fullCorners(),angle:0,brightness:0,contrast:0})};
    if(!page.edit){const found=detectDocument(raw);photoState.edit.corners=found.points;$("photoStatus").textContent=found.found?"문서 테두리를 제안했습니다. 네 모서리를 확인해 주세요.":"테두리를 확실히 찾지 못했습니다. 모서리를 직접 맞춰 주세요.";}else $("photoStatus").textContent="현재 보정 설정입니다. 원본에서 다시 조정할 수 있습니다.";
    syncPhotoControls();drawEdges();previewPhoto();
  }catch(e){$("photoStatus").textContent=e.message;}
}
function syncPhotoControls(){
  if(!photoState)return;for(const [id,key] of [["photoAngle","angle"],["photoBrightness","brightness"],["photoContrast","contrast"]])$(id).value=photoState.edit[key]||0;
  $("cornerInputs").replaceChildren();
  photoState.edit.corners.forEach((point,i)=>{const row=el("div",undefined,"cornerRow");row.append(el("span",["왼쪽 위","오른쪽 위","오른쪽 아래","왼쪽 아래"][i]));for(let axis=0;axis<2;axis++){const label=el("label",axis?"Y %":"X %"),input=el("input");input.type="number";input.min=0;input.max=100;input.step=.1;input.value=(point[axis]*100).toFixed(1);input.setAttribute("aria-label",`${i+1}번 모서리 ${axis?"Y":"X"}`);input.onchange=()=>{const v=Number(input.value);if(!Number.isFinite(v)||v<0||v>100)return;photoState.edit.corners[i][axis]=v/100;drawEdges();previewPhoto();};label.append(input);row.append(label);}$("cornerInputs").append(row);});
}
function drawEdges(){
  if(!photoState)return;const {raw,edit}=photoState,c=$("edgeCanvas"),k=Math.min(1,700/Math.max(raw.width,raw.height));c.width=Math.round(raw.width*k);c.height=Math.round(raw.height*k);const ctx=c.getContext("2d");ctx.drawImage(raw,0,0,c.width,c.height);ctx.strokeStyle="#ff8a27";ctx.lineWidth=3;ctx.beginPath();edit.corners.forEach(([x,y],i)=>i?ctx.lineTo(x*c.width,y*c.height):ctx.moveTo(x*c.width,y*c.height));ctx.closePath();ctx.stroke();edit.corners.forEach(([x,y],i)=>{ctx.fillStyle="#fff";ctx.beginPath();ctx.arc(x*c.width,y*c.height,10,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.fillStyle="#172f4d";ctx.font="bold 12px sans-serif";ctx.textAlign="center";ctx.fillText(String(i+1),x*c.width,y*c.height+4);});
}
function previewPhoto(){
  clearTimeout(previewTimer);$("photoApply").disabled=true;
  $("angleValue").textContent=$("photoAngle").value+"°";$("brightnessValue").textContent=$("photoBrightness").value;$("contrastValue").textContent=$("photoContrast").value;
  previewTimer=setTimeout(()=>{if(!photoState)return;try{const result=warpDocument(photoState.raw,photoState.edit,800),target=$("photoPreview");target.width=result.width;target.height=result.height;target.getContext("2d").drawImage(result,0,0);result.width=result.height=1;$("photoApply").disabled=false;}catch(e){$("photoStatus").textContent=e.message;}},80);
}
const edgeCanvas=$("edgeCanvas");
edgeCanvas.onpointerdown=e=>{if(!photoState)return;const r=edgeCanvas.getBoundingClientRect(),x=(e.clientX-r.left)/r.width,y=(e.clientY-r.top)/r.height;let distance=Infinity;photoState.edit.corners.forEach((p,i)=>{const d=Math.hypot((p[0]-x)*r.width,(p[1]-y)*r.height);if(d<distance){distance=d;dragCorner=i;}});if(distance>45){dragCorner=-1;return;}edgeCanvas.setPointerCapture(e.pointerId);e.preventDefault();};
edgeCanvas.onpointermove=e=>{if(dragCorner<0||!photoState)return;const r=edgeCanvas.getBoundingClientRect();photoState.edit.corners[dragCorner]=[Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];drawEdges();previewPhoto();};
edgeCanvas.onpointerup=()=>{dragCorner=-1;syncPhotoControls();};edgeCanvas.onpointercancel=()=>dragCorner=-1;
for(const [id,key] of [["photoAngle","angle"],["photoBrightness","brightness"],["photoContrast","contrast"]])$(id).oninput=()=>{if(photoState){photoState.edit[key]=Number($(id).value);previewPhoto();}};
$("autoEdges").onclick=()=>{if(!photoState)return;const found=detectDocument(photoState.raw);photoState.edit.corners=found.points;$("photoStatus").textContent=found.found?"테두리를 제안했습니다. 확인 후 보정 적용을 눌러 주세요.":"테두리를 확실히 찾지 못했습니다. 직접 모서리를 맞춰 주세요.";syncPhotoControls();drawEdges();previewPhoto();};
$("fullEdges").onclick=()=>{if(photoState){photoState.edit.corners=fullCorners();syncPhotoControls();drawEdges();previewPhoto();}};
$("photoRestore").onclick=()=>{if(photoState){photoState.edit={corners:fullCorners(),angle:0,brightness:0,contrast:0};photoState.restore=true;syncPhotoControls();drawEdges();previewPhoto();$("photoStatus").textContent="원본 상태입니다. 보정 적용을 누르면 복원합니다.";}};
$("photoApply").onclick=()=>{if(!photoState||!validCorners(photoState.edit.corners))return;const {page,edit}=photoState;commit(()=>{page.edit=structuredClone(edit);if(JSON.stringify(edit.corners)===JSON.stringify(fullCorners())&&!edit.angle&&!edit.brightness&&!edit.contrast)delete page.edit;});$("photoDialog").close();if(comparison)drawComparison();};
$("photoClose").onclick=()=>$("photoDialog").close();
$("photoDialog").addEventListener("close",()=>{photoEpoch++;clearTimeout(previewTimer);if(photoState)photoState.raw.width=photoState.raw.height=1;photoState=null;dragCorner=-1;});

render();
$("editor").inert = false;
