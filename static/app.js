"use strict";

const socket = io({
  transports: ["websocket", "polling"],
});

const $ = (id) => document.getElementById(id);

const canvas = $("board");
const ctx = canvas.getContext("2d");

const MARGIN_X = 60;
const MARGIN_Y = 60;
const CELL_X = 62.5;
const CELL_Y = 62;

let session = null;
let state = null;

let selected = null;
let legalMoves = [];

let toastTimer = null;


/* =========================================================
   本地会话
========================================================= */

function savedSession() {
  try {
    return JSON.parse(
      localStorage.getItem("jieqi-session")
    );
  } catch (_) {
    return null;
  }
}

function payload(extra = {}) {
  return {
    room: session?.room,
    token: session?.token,
    ...extra,
  };
}


/* =========================================================
   通用 UI
========================================================= */

function showToast(message) {
  const el = $("toast");

  el.textContent = message;
  el.classList.add("show");

  clearTimeout(toastTimer);

  toastTimer = setTimeout(() => {
    el.classList.remove("show");
  }, 2600);
}

function setConnected(connected) {
  const el = $("connectionBadge");

  el.classList.toggle(
    "offline",
    !connected
  );

  el.lastChild.textContent =
    connected
      ? "已连接"
      : "连接断开";
}

function enterGame() {
  $("lobby").classList.add("hidden");
  $("game").classList.remove("hidden");
}

function leaveGame() {
  localStorage.removeItem(
    "jieqi-session"
  );

  session = null;
  state = null;
  selected = null;
  legalMoves = [];

  $("game").classList.add("hidden");
  $("lobby").classList.remove("hidden");

  draw();
}


/* =========================================================
   大厅
========================================================= */

$("createBtn").onclick = () => {
  socket.emit(
    "create_room",
    {
      name: $("playerName").value,
    }
  );
};

$("joinBtn").onclick = () => {
  socket.emit(
    "join_room",
    {
      name: $("playerName").value,
      room: $("roomInput").value.trim(),
    }
  );
};

$("roomInput").addEventListener(
  "keydown",
  (event) => {
    if (event.key === "Enter") {
      $("joinBtn").click();
    }
  }
);

$("leaveBtn").onclick = leaveGame;


/* =========================================================
   房间号
========================================================= */

$("copyRoom").onclick = async () => {
  if (!session?.room) {
    return;
  }

  try {
    await navigator.clipboard.writeText(
      session.room
    );

    showToast("房间号已复制");
  } catch (_) {
    showToast(
      `房间号：${session.room}`
    );
  }
};


/* =========================================================
   悔棋 / 重开
========================================================= */

$("undoBtn").onclick = () => {
  socket.emit(
    "request_action",
    payload({
      kind: "undo",
    })
  );
};

$("restartBtn").onclick = () => {
  socket.emit(
    "request_action",
    payload({
      kind: "restart",
    })
  );
};

$("acceptBtn").onclick = () => {
  socket.emit(
    "respond_action",
    payload({
      accepted: true,
    })
  );

  $("proposal").classList.add("hidden");
};

$("rejectBtn").onclick = () => {
  socket.emit(
    "respond_action",
    payload({
      accepted: false,
    })
  );

  $("proposal").classList.add("hidden");
};


/* =========================================================
   被吃暗棋身份开关
========================================================= */

$("hideCapturedDarkToggle").addEventListener(
  "change",
  (event) => {
    if (!session) {
      return;
    }

    if (session.side !== "red") {
      showToast(
        "只有房主可以修改该设置"
      );

      event.target.checked =
        !!state?.settings?.hide_captured_dark;

      return;
    }

    socket.emit(
      "set_hide_captured_dark",
      payload({
        enabled: event.target.checked,
      })
    );
  }
);


/* =========================================================
   Socket.IO
========================================================= */

socket.on(
  "connect",
  () => {
    setConnected(true);

    const saved = savedSession();

    if (
      saved?.room
      && saved?.token
    ) {
      socket.emit(
        "resume_session",
        saved
      );
    }
  }
);

socket.on(
  "disconnect",
  () => {
    setConnected(false);
  }
);

socket.on(
  "session",
  (data) => {
    session = data;

    localStorage.setItem(
      "jieqi-session",
      JSON.stringify(data)
    );

    $("playerName").value =
      data.name;

    enterGame();

    if (data.resumed) {
      showToast("已恢复对局");
    }
  }
);

socket.on(
  "server_error",
  (data) => {
    showToast(
      data.message || "操作失败"
    );
  }
);

socket.on(
  "legal_moves",
  (data) => {
    if (
      !state
      || data.revision !== state.revision
    ) {
      return;
    }

    selected = data.start;
    legalMoves = data.moves || [];

    draw();
  }
);

socket.on(
  "game_state",
  (data) => {
    state = data;

    selected = null;
    legalMoves = [];

    enterGame();

    updateUI();
    draw();
  }
);


/* =========================================================
   整体 UI 更新
========================================================= */

function updateUI() {
  if (!state) {
    return;
  }

  $("copyRoom").textContent =
    state.room;

  $("mySide").textContent =
    session?.side === "red"
      ? "红方"
      : "黑方";

  for (const side of ["red", "black"]) {
    const player =
      state.players?.[side];

    const el =
      $(`${side}Player`);

    el.querySelector(
      "strong"
    ).textContent =
      player?.name
      || "等待加入";

    el.classList.toggle(
      "online",
      !!player?.connected
    );
  }

  const turnName =
    state.turn === "red"
      ? "红方"
      : "黑方";

  $("turnText").textContent =
    state.winner
      ? `${
          state.winner === "red"
            ? "红"
            : "黑"
        }方获胜`
      : (
          state.ready
            ? `${turnName}行棋`
            : "等待玩家加入"
        );

  $("statusText").textContent =
    state.status || "";

  $("waitingOverlay").classList.toggle(
    "hidden",
    !!state.ready
  );

  $("undoBtn").disabled =
    !state.ready
    || !state.can_undo
    || !!state.proposal;

  $("restartBtn").disabled =
    !state.ready
    || !!state.proposal;

  updateSettingsUI();
  updateCheckUI();

  renderCaptured("red");
  renderCaptured("black");

  updateProposalUI();
}


/* =========================================================
   房间设置 UI
========================================================= */

function updateSettingsUI() {
  const hidden =
    !!state?.settings?.hide_captured_dark;

  const toggle =
    $("hideCapturedDarkToggle");

  toggle.checked = hidden;

  const isHost =
    session?.side === "red";

  toggle.disabled =
    !isHost;

  $("hideCapturedDarkText").textContent =
    hidden
      ? "仅吃子方可见"
      : "双方公开";

  $("settingsHint").textContent =
    isHost
      ? "你是房主，可修改此规则"
      : "仅房主可修改";

  $("capturedHint").textContent =
    hidden
      ? "暗棋被吃后，仅吃子方可查看真实身份"
      : "被吃棋子的真实身份双方可见";
}


/* =========================================================
   将军提示
========================================================= */

function updateCheckUI() {
  const banner =
    $("checkBanner");

  const redCheck =
    !!state?.check?.red;

  const blackCheck =
    !!state?.check?.black;

  if (
    !redCheck
    && !blackCheck
  ) {
    banner.classList.add("hidden");
    return;
  }

  banner.classList.remove("hidden");

  if (
    redCheck
    && blackCheck
  ) {
    banner.textContent =
      "双方均被将军！";
  } else if (redCheck) {
    banner.textContent =
      "红方被将军！";
  } else {
    banner.textContent =
      "黑方被将军！";
  }
}


/* =========================================================
   悔棋 / 重开弹窗
========================================================= */

function updateProposalUI() {
  const proposal =
    state.proposal;

  if (
    proposal
    && proposal.by !== session?.side
  ) {
    const isUndo =
      proposal.kind === "undo";

    $("proposalTitle").textContent =
      isUndo
        ? "对方请求悔棋"
        : "对方请求重新开局";

    $("proposalText").textContent =
      isUndo
        ? "同意后将恢复上一步，包括棋子的明暗状态。"
        : "同意后双方将重新洗牌。";

    $("proposal").classList.remove("hidden");
  } else {
    $("proposal").classList.add("hidden");
  }
}


/* =========================================================
   被吃棋子
========================================================= */

function renderCaptured(side) {
  const list =
    (state?.captured || []).filter(
      (piece) =>
        piece.captured_from_side === side
    );

  $(`${side}Count`).textContent =
    list.length;

  const box =
    $(`${side}Captured`);

  box.replaceChildren();

  for (const piece of list) {
    const el =
      document.createElement("span");

    if (piece.hidden) {
      el.className =
        "captured-piece hidden-piece";

      el.textContent = "";

      el.title =
        "该暗棋身份对你保密";
    } else {
      el.className =
        `captured-piece ${piece.color}`;

      el.textContent =
        piece.name;

      el.title =
        `${piece.color === "red" ? "红" : "黑"}方棋子`;
    }

    box.appendChild(el);
  }
}


/* =========================================================
   点击棋盘
========================================================= */

canvas.addEventListener(
  "click",
  (event) => {
    if (
      !state?.ready
      || state.winner
      || state.turn !== session?.side
    ) {
      return;
    }

    const rect =
      canvas.getBoundingClientRect();

    const x =
      (
        event.clientX
        - rect.left
      )
      * canvas.width
      / rect.width;

    const y =
      (
        event.clientY
        - rect.top
      )
      * canvas.height
      / rect.height;

    const col =
      Math.round(
        (x - MARGIN_X)
        / CELL_X
      );

    const row =
      Math.round(
        (y - MARGIN_Y)
        / CELL_Y
      );

    if (
      row < 0
      || row > 9
      || col < 0
      || col > 8
    ) {
      return;
    }

    if (
      Math.abs(
        x
        - (
          MARGIN_X
          + col * CELL_X
        )
      ) > 28
    ) {
      return;
    }

    if (
      Math.abs(
        y
        - (
          MARGIN_Y
          + row * CELL_Y
        )
      ) > 28
    ) {
      return;
    }

    const canMoveHere =
      legalMoves.some(
        (pos) =>
          pos[0] === row
          && pos[1] === col
      );

    if (
      selected
      && canMoveHere
    ) {
      socket.emit(
        "move_piece",
        payload({
          start: selected,
          end: [row, col],
        })
      );

      return;
    }

    const piece =
      state.pieces.find(
        (item) =>
          item.row === row
          && item.col === col
      );

    if (
      piece?.control_side === session.side
    ) {
      socket.emit(
        "select_piece",
        payload({
          row,
          col,
        })
      );
    } else {
      selected = null;
      legalMoves = [];

      draw();
    }
  }
);


/* =========================================================
   Canvas 绘制
========================================================= */

function draw() {
  ctx.clearRect(
    0,
    0,
    canvas.width,
    canvas.height
  );

  const left =
    MARGIN_X;

  const right =
    MARGIN_X + 8 * CELL_X;

  const top =
    MARGIN_Y;

  const bottom =
    MARGIN_Y + 9 * CELL_Y;

  ctx.fillStyle =
    "#ddb574";

  ctx.fillRect(
    0,
    0,
    canvas.width,
    canvas.height
  );

  ctx.strokeStyle =
    "#4d2e1b";

  ctx.lineWidth = 2;

  for (
    let row = 0;
    row < 10;
    row++
  ) {
    line(
      left,
      top + row * CELL_Y,
      right,
      top + row * CELL_Y
    );
  }

  for (
    let col = 0;
    col < 9;
    col++
  ) {
    const x =
      left + col * CELL_X;

    if (
      col === 0
      || col === 8
    ) {
      line(
        x,
        top,
        x,
        bottom
      );
    } else {
      line(
        x,
        top,
        x,
        top + 4 * CELL_Y
      );

      line(
        x,
        top + 5 * CELL_Y,
        x,
        bottom
      );
    }
  }

  line(
    left + 3 * CELL_X,
    top,
    left + 5 * CELL_X,
    top + 2 * CELL_Y
  );

  line(
    left + 5 * CELL_X,
    top,
    left + 3 * CELL_X,
    top + 2 * CELL_Y
  );

  line(
    left + 3 * CELL_X,
    top + 7 * CELL_Y,
    left + 5 * CELL_X,
    bottom
  );

  line(
    left + 5 * CELL_X,
    top + 7 * CELL_Y,
    left + 3 * CELL_X,
    bottom
  );

  ctx.fillStyle =
    "#51331f";

  ctx.font =
    "bold 29px 'KaiTi','STKaiti',serif";

  ctx.textAlign =
    "center";

  ctx.textBaseline =
    "middle";

  ctx.fillText(
    "楚 河",
    left + 2 * CELL_X,
    top + 4.5 * CELL_Y
  );

  ctx.fillText(
    "漢 界",
    left + 6 * CELL_X,
    top + 4.5 * CELL_Y
  );

  if (!state) {
    return;
  }

  drawLastMove();

  for (const piece of state.pieces) {
    drawPiece(piece);
  }

  drawCheckHighlight();

  for (
    const [row, col]
    of legalMoves
  ) {
    const x =
      left + col * CELL_X;

    const y =
      top + row * CELL_Y;

    const occupied =
      state.pieces.some(
        (piece) =>
          piece.row === row
          && piece.col === col
      );

    ctx.beginPath();

    ctx.arc(
      x,
      y,
      occupied ? 31 : 7,
      0,
      Math.PI * 2
    );

    if (occupied) {
      ctx.strokeStyle =
        "#26715b";

      ctx.lineWidth = 4;

      ctx.stroke();
    } else {
      ctx.fillStyle =
        "#26715b";

      ctx.fill();
    }
  }
}


/* =========================================================
   上一步起点 / 终点
========================================================= */

function drawLastMove() {
  const last =
    state?.last_move;

  if (
    !last?.from
    || !last?.to
  ) {
    return;
  }

  const [
    fromRow,
    fromCol,
  ] = last.from;

  const [
    toRow,
    toCol,
  ] = last.to;

  const fromX =
    MARGIN_X
    + fromCol * CELL_X;

  const fromY =
    MARGIN_Y
    + fromRow * CELL_Y;

  const toX =
    MARGIN_X
    + toCol * CELL_X;

  const toY =
    MARGIN_Y
    + toRow * CELL_Y;

  ctx.save();

  /*
   * 起点：
   * 蓝灰色方框 + 中心点
   */

  ctx.strokeStyle =
    "rgba(55, 91, 132, 0.95)";

  ctx.lineWidth = 4;

  ctx.strokeRect(
    fromX - 16,
    fromY - 16,
    32,
    32
  );

  ctx.beginPath();

  ctx.arc(
    fromX,
    fromY,
    5,
    0,
    Math.PI * 2
  );

  ctx.fillStyle =
    "rgba(55, 91, 132, 0.95)";

  ctx.fill();

  /*
   * 终点：
   * 金棕色圆环
   */

  ctx.beginPath();

  ctx.arc(
    toX,
    toY,
    34,
    0,
    Math.PI * 2
  );

  ctx.strokeStyle =
    "rgba(193, 114, 26, 0.96)";

  ctx.lineWidth = 5;

  ctx.stroke();

  ctx.restore();
}


/* =========================================================
   将军高亮
========================================================= */

function drawCheckHighlight() {
  if (!state?.check) {
    return;
  }

  for (
    const side
    of ["red", "black"]
  ) {
    if (!state.check[side]) {
      continue;
    }

    const king =
      state.pieces.find(
        (piece) =>
          piece.revealed
          && (
            piece.name === "帥"
            || piece.name === "將"
          )
          && piece.color === side
      );

    if (!king) {
      continue;
    }

    const x =
      MARGIN_X
      + king.col * CELL_X;

    const y =
      MARGIN_Y
      + king.row * CELL_Y;

    ctx.save();

    ctx.beginPath();

    ctx.arc(
      x,
      y,
      36,
      0,
      Math.PI * 2
    );

    ctx.strokeStyle =
      "rgba(190, 28, 28, 0.96)";

    ctx.lineWidth = 6;

    ctx.stroke();

    ctx.restore();
  }
}


/* =========================================================
   画线
========================================================= */

function line(
  x1,
  y1,
  x2,
  y2
) {
  ctx.beginPath();

  ctx.moveTo(
    x1,
    y1
  );

  ctx.lineTo(
    x2,
    y2
  );

  ctx.stroke();
}


/* =========================================================
   绘制棋子
========================================================= */

function drawPiece(p) {
  const x =
    MARGIN_X
    + p.col * CELL_X;

  const y =
    MARGIN_Y
    + p.row * CELL_Y;

  const isSelected =
    selected?.[0] === p.row
    && selected?.[1] === p.col;

  ctx.save();

  ctx.shadowColor =
    "rgba(50,25,8,.35)";

  ctx.shadowBlur = 7;
  ctx.shadowOffsetY = 3;

  ctx.beginPath();

  ctx.arc(
    x,
    y,
    27,
    0,
    Math.PI * 2
  );

  ctx.fillStyle =
    "#f3dca8";

  ctx.fill();

  ctx.shadowColor =
    "transparent";

  ctx.strokeStyle =
    isSelected
      ? "#d99b22"
      : "#674024";

  ctx.lineWidth =
    isSelected
      ? 5
      : 3;

  ctx.stroke();

  ctx.beginPath();

  ctx.arc(
    x,
    y,
    22,
    0,
    Math.PI * 2
  );

  ctx.strokeStyle =
    "#b98b52";

  ctx.lineWidth = 1;

  ctx.stroke();

  if (p.revealed) {
    ctx.fillStyle =
      p.color === "red"
        ? "#a21e1b"
        : "#211b17";

    ctx.font =
      "bold 29px 'KaiTi','STKaiti',serif";

    ctx.textAlign =
      "center";

    ctx.textBaseline =
      "middle";

    ctx.fillText(
      p.name,
      x,
      y + 1
    );
  } else {
    /*
     * 暗棋不显示文字
     */

    ctx.fillStyle =
      "rgba(83,48,26,.12)";

    ctx.beginPath();

    ctx.arc(
      x,
      y,
      17,
      0,
      Math.PI * 2
    );

    ctx.fill();
  }

  ctx.restore();
}


/* =========================================================
   初始绘制
========================================================= */

draw();