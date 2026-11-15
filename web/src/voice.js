// Speech in and out. Uses the browser's Web Speech API (Chrome, Edge,
// Safari). If it isn't available, or the page isn't allowed the microphone,
// the typed command bar still works with the same commands.

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export function createVoice({ onText, onState, onInterim }) {
  let rec = null;
  let listening = false;

  function listen() {
    if (!Recognition) {
      onState("unsupported");
      return;
    }
    if (listening) {
      rec?.stop();
      return;
    }
    rec = new Recognition();
    rec.lang = "en-US";
    rec.interimResults = true; // show the words live while the person is still speaking
    rec.maxAlternatives = 1;
    rec.onstart = () => { listening = true; onState("listening"); };
    rec.onend = () => { listening = false; onState("idle"); };
    rec.onerror = (e) => { listening = false; onState(e.error === "not-allowed" ? "blocked" : "error"); };
    rec.onresult = (e) => {
      let finalText = "", live = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t; else live += t;
      }
      if (live) onInterim?.(live);
      if (finalText) onText(finalText.trim());
    };
    try { rec.start(); } catch { onState("error"); }
  }

  function say(text) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.03;
    window.speechSynthesis.speak(u);
  }

  return { listen, say, supported: !!Recognition };
}
