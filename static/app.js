"use strict";

const socket = io({ transports: ["websocket", "polling"] });
const $ = (id) => document.getElementById(id);
const canvas = $("board");
const ctx = canvas.getContext("2d");
const MARGIN_X = 60, MARGIN_Y = 60, CELL_X = 62.5, CELL_Y = 62;
let session = null;
let state = null;
let selected = null;
let legalMoves = [];
let toastTimer = null;

function savedSession() {
  try { return JSON.parse(localStorage.getItem("jieqi-session")); } catch (_) { return null; }
}
function payload(extra = {}) { return { room: session?.room, token: session?.token, ...extra }; }
function showToast(message) {
  const el = $("toast"); el.textContent = message; el.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}
function setConnected(connected) {
  const el = $("connectionBadge");
  el.classList.toggle("offline", !connected);
  el.lastChild.textContent = connected ? "已连接" : "连接断开";
}
function enterGame() { $("lobby").classList.add("hidden"); $("game").classList.remove("hidden"); }
function leaveGame() {
  localStorage.removeItem("jieqi-session"); session = null; state = null; selected = null;
  $("game").classList.add("hidden"); $("lobby").classList.remove("hidden");
}

$("createBtn").onclick = () => socket.emit("create_room", { name: $("playerName").value });
$("joinBtn").onclick = () => socket.emit("join_room", { name: $("playerName").value, room: $("roomInput").value.trim() });
$("roomInput").addEventListener("keydown", e => { if (e.key === "Enter") $("joinBtn").click(); });
$("leaveBtn").onclick = leaveGame;
$("copyRoom").onclick = async () => {
  try { await navigator.clipboard.writeText(session.room); showToast("房间号已复制"); }
  catch (_) { showToast(`房间号：${session.room}`); }
};
$("undoBtn").onclick = () => socket.emit("request_action", payload({ kind: "undo" }));
$("restartBtn").onclick = () => socket.emit("request_action", payload({ kind: "restart" }));
$("acceptBtn").onclick = () => { socket.emit("respond_action", payload({ accepted: true })); $("proposal").classList.add("hidden"); };
$("rejectBtn").onclick = () => { socket.emit("respond_action", payload({ accepted: false })); $("proposal").classList.add("hidden"); };

socket.on("connect", () => {
  setConnected(true);
  const saved = savedSession();
  if (saved?.room && saved?.token) socket.emit("resume_session", saved);
});
socket.on("disconnect", () => setConnected(false));
socket.on("session", data => {
  session = data; localStorage.setItem("jieqi-session", JSON.stringify(data));
  $("playerName").value = data.name; enterGame();
  if (data.resumed) showToast("已恢复对局");
});
socket.on("server_error", data => showToast(data.message || "操作失败"));
socket.on("legal_moves", data => {
  if (!state || data.revision !== state.revision) return;
  selected = data.start; legalMoves = data.moves; draw();
});
socket.on("game_state", data => {
  state = data; selected = null; legalMoves = []; enterGame(); updateUI(); draw();
});

function updateUI() {
  $("copyRoom").textContent = state.room;
  $("mySide").textContent = session?.side === "red" ? "红方" : "黑方";
  for (const side of ["red", "black"]) {
    const player = state.players[side]; const el = $(`${side}Player`);
    el.querySelector("strong").textContent = player?.name || "等待加入";
    el.classList.toggle("online", !!player?.connected);
  }
  const turnName = state.turn === "red" ? "红方" : "黑方";
  $("turnText").textContent = state.winner ? `${state.winner === "red" ? "红" : "黑"}方获胜` : (state.ready ? `${turnName}行棋` : "等待玩家加入");
  $("statusText").textContent = state.status;
  $("waitingOverlay").classList.toggle("hidden", state.ready);
  $("undoBtn").disabled = !state.ready || !state.can_undo || !!state.proposal;
  $("restartBtn").disabled = !state.ready || !!state.proposal;
  renderCaptured("red"); renderCaptured("black");
  const proposal = state.proposal;
  if (proposal && proposal.by !== session?.side) {
    const isUndo = proposal.kind === "undo";
    $("proposalTitle").textContent = isUndo ? "对方请求悔棋" : "对方请求重新开局";
    $("proposalText").textContent = isUndo ? "同意后将恢复上一步，包括棋子的明暗状态。" : "同意后双方将重新洗牌。";
    $("proposal").classList.remove("hidden");
  } else $("proposal").classList.add("hidden");
}
function renderCaptured(color) {
  const list = state.captured.filter(p => p.color === color);
  $(`${color}Count`).textContent = list.length;
  const box = $(`${color}Captured`); box.replaceChildren();
  for (const piece of list) {
    const el = document.createElement("span"); el.className = `captured-piece ${color}`;
    el.textContent = piece.name; box.appendChild(el);
  }
}

canvas.addEventListener("click", event => {
  if (!state?.ready || state.winner || state.turn !== session?.side) return;
  const rect = canvas.getBoundingClientRect();
  const x = (event.clientX - rect.left) * canvas.width / rect.width;
  const y = (event.clientY - rect.top) * canvas.height / rect.height;
  const col = Math.round((x - MARGIN_X) / CELL_X), row = Math.round((y - MARGIN_Y) / CELL_Y);
  if (row < 0 || row > 9 || col < 0 || col > 8 || Math.abs(x-(MARGIN_X+col*CELL_X)) > 28 || Math.abs(y-(MARGIN_Y+row*CELL_Y)) > 28) return;
  const move = legalMoves.some(p => p[0] === row && p[1] === col);
  if (selected && move) socket.emit("move_piece", payload({ start: selected, end: [row, col] }));
  else {
    const piece = state.pieces.find(p => p.row === row && p.col === col);
    if (piece?.control_side === session.side) socket.emit("select_piece", payload({ row, col }));
    else { selected = null; legalMoves = []; draw(); }
  }
});

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const left = MARGIN_X, right = MARGIN_X + 8*CELL_X, top = MARGIN_Y, bottom = MARGIN_Y + 9*CELL_Y;
  ctx.fillStyle = "#ddb574"; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "#4d2e1b"; ctx.lineWidth = 2;
  for (let row=0; row<10; row++) line(left, top+row*CELL_Y, right, top+row*CELL_Y);
  for (let col=0; col<9; col++) {
    const x = left+col*CELL_X;
    if (col===0 || col===8) line(x,top,x,bottom);
    else { line(x,top,x,top+4*CELL_Y); line(x,top+5*CELL_Y,x,bottom); }
  }
  line(left+3*CELL_X,top,left+5*CELL_X,top+2*CELL_Y); line(left+5*CELL_X,top,left+3*CELL_X,top+2*CELL_Y);
  line(left+3*CELL_X,top+7*CELL_Y,left+5*CELL_X,bottom); line(left+5*CELL_X,top+7*CELL_Y,left+3*CELL_X,bottom);
  ctx.fillStyle = "#51331f"; ctx.font = "bold 29px 'KaiTi','STKaiti',serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText("楚 河", left+2*CELL_X, top+4.5*CELL_Y); ctx.fillText("漢 界", left+6*CELL_X, top+4.5*CELL_Y);
  if (!state) return;
  for (const p of state.pieces) drawPiece(p);
  for (const [row,col] of legalMoves) {
    const x=left+col*CELL_X, y=top+row*CELL_Y, occupied=state.pieces.some(p=>p.row===row&&p.col===col);
    ctx.beginPath(); ctx.arc(x,y,occupied?31:7,0,Math.PI*2);
    if (occupied) { ctx.strokeStyle="#26715b"; ctx.lineWidth=4; ctx.stroke(); }
    else { ctx.fillStyle="#26715b"; ctx.fill(); }
  }
}
function line(x1,y1,x2,y2) { ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke(); }
function drawPiece(p) {
  const x=MARGIN_X+p.col*CELL_X, y=MARGIN_Y+p.row*CELL_Y, isSelected=selected?.[0]===p.row&&selected?.[1]===p.col;
  ctx.save(); ctx.shadowColor="rgba(50,25,8,.35)"; ctx.shadowBlur=7; ctx.shadowOffsetY=3;
  ctx.beginPath(); ctx.arc(x,y,27,0,Math.PI*2); ctx.fillStyle="#f3dca8"; ctx.fill();
  ctx.shadowColor="transparent"; ctx.strokeStyle=isSelected?"#d99b22":"#674024"; ctx.lineWidth=isSelected?5:3; ctx.stroke();
  ctx.beginPath(); ctx.arc(x,y,22,0,Math.PI*2); ctx.strokeStyle="#b98b52"; ctx.lineWidth=1; ctx.stroke();
  if (p.revealed) { ctx.fillStyle=p.color==="red"?"#a21e1b":"#211b17"; ctx.font="bold 29px 'KaiTi','STKaiti',serif"; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText(p.name,x,y+1); }
  else { ctx.fillStyle="rgba(83,48,26,.12)"; ctx.beginPath(); ctx.arc(x,y,17,0,Math.PI*2); ctx.fill(); }
  ctx.restore();
}
draw();
