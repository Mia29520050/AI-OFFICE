import { createLive2D } from "./index.mjs";

const CORE_URL = "/assets/live2d/live2dcubismcore.min.js";

export class Live2DStageController {
  constructor() {
    this._instance = null;
    this._cleanupLipSync = null;
    this._mountToken = 0;
    this._modelUrl = "";
    this._fit = "upper-body";
    this._moodMap = {};
    this._lastMoodExpr = null;
    this._manualExpr = "";
    this._speaking = false;
    this._speakUntil = 0;
    this._lastComment = "";
  }

  get isReady() {
    return Boolean(this._instance && this._instance.getState()?.status === "ready");
  }

  async mount({ container, fallbackEl, modelUrl, moodMap = {}, fit = "upper-body", onStatus = () => {} }) {
    if (!container) return false;
    if (!modelUrl) {
      this.dispose();
      if (fallbackEl) fallbackEl.hidden = false;
      container.hidden = true;
      onStatus("svg", "");
      return false;
    }

    if (this._instance && this._modelUrl === modelUrl) {
      this._moodMap = moodMap;
      if (fit && this._fit !== fit) {
        this._fit = fit;
        try { this._instance.setFit(fit); } catch {}
      }
      if (fallbackEl) fallbackEl.hidden = true;
      container.hidden = false;
      return true;
    }

    const token = ++this._mountToken;
    this._disposeCurrent();
    this._modelUrl = modelUrl;
    this._fit = fit || "upper-body";
    this._moodMap = moodMap || {};
    this._manualExpr = "";
    this._lastMoodExpr = null;

    if (fallbackEl) fallbackEl.hidden = false;
    container.hidden = true;
    container.innerHTML = "";
    onStatus("loading", "Đang tải model Live2D...");

    try {
      const inst = await createLive2D({
        container,
        coreUrl: CORE_URL,
        src: modelUrl,
        fit: this._fit,
        followPointer: true,
      });

      if (token !== this._mountToken) {
        try { inst.dispose(); } catch {}
        return false;
      }

      this._instance = inst;
      this._cleanupLipSync = inst.addLipSync({
        driver: {
          isSpeaking: () => Boolean(this._speaking || performance.now() < this._speakUntil),
          getMouthOpen: () => {
            if (!this._speaking && performance.now() >= this._speakUntil) return 0;
            const t = performance.now();
            return 0.16 + 0.64 * Math.abs(Math.sin(t * 0.017) * (0.55 + 0.45 * Math.cos(t * 0.009)));
          },
        },
      });

      if (fallbackEl) fallbackEl.hidden = true;
      container.hidden = false;
      onStatus("ready", "");
      return true;
    } catch (err) {
      if (token === this._mountToken) {
        this._modelUrl = "";
        container.innerHTML = "";
        container.hidden = true;
        if (fallbackEl) fallbackEl.hidden = false;
        onStatus("fallback", err?.message || "WebGL2/Live2D không khả dụng; dùng SVG dự phòng.");
      }
      return false;
    }
  }

  setFit(fit) {
    this._fit = fit || "upper-body";
    if (this._instance) {
      try { this._instance.setFit(this._fit); } catch {}
    }
  }

  setExpression(exprId) {
    this._manualExpr = exprId || "";
    this._lastMoodExpr = this._manualExpr;
    if (!this._instance) return;
    if (!exprId) {
      try { this._instance.clearExpression(); } catch {}
      return;
    }
    this._instance.expression(exprId).catch(() => {});
  }

  syncState({ mood = "happy", speaking = false, comment = "", actionPoint = null } = {}) {
    this._speaking = Boolean(speaking);
    if (comment && comment !== this._lastComment) {
      this._lastComment = comment;
      this._speakUntil = performance.now() + Math.min(3400, Math.max(1400, comment.length * 42));
    }
    if (!this._instance) return;

    if (!this._manualExpr) {
      const targetExpr = this._moodMap[mood] || "";
      if (targetExpr !== this._lastMoodExpr) {
        this._lastMoodExpr = targetExpr;
        if (targetExpr) {
          this._instance.expression(targetExpr).catch(() => {});
        } else {
          try { this._instance.clearExpression(); } catch {}
        }
      }
    }

    if (actionPoint && Number.isFinite(actionPoint.x) && Number.isFinite(actionPoint.y)) {
      try {
        const w = this._instance.getState()?.render?.width || 240;
        const h = this._instance.getState()?.render?.height || 300;
        this._instance.focus((actionPoint.x / 1000) * w, (actionPoint.y / 1000) * h);
      } catch {}
    }
  }

  _disposeCurrent() {
    if (this._cleanupLipSync) {
      try { this._cleanupLipSync(); } catch {}
      this._cleanupLipSync = null;
    }
    if (this._instance) {
      try { this._instance.dispose(); } catch {}
      this._instance = null;
    }
  }

  dispose() {
    this._mountToken++;
    this._modelUrl = "";
    this._disposeCurrent();
  }
}

window.AIOfficeLive2D = new Live2DStageController();
