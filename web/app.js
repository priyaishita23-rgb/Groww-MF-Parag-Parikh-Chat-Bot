/* Chat widget: streaming, quick-reply chips, and the card renderers.
   Vanilla, no framework, no build step. */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  const widget = $("widget"), launcher = $("launcher"), thread = $("thread"),
        scroll = $("scroll"), chipBar = $("chips"), input = $("input"),
        form = $("composer"), send = $("send"), who = $("who"),
        profileSel = $("profile");

  let sessionId = localStorage.getItem("sid") || null;
  let busy = false;
  let greeted = false;

  /* ------------------------------ helpers ------------------------------ */
  const money = (v) => {
    const neg = v < 0;
    const [w, f] = Math.abs(v).toFixed(2).split(".");
    let out = w;
    if (w.length > 3) {
      const tail = w.slice(-3);
      let head = w.slice(0, -3), parts = [];
      while (head.length > 2) { parts.unshift(head.slice(-2)); head = head.slice(0, -2); }
      if (head) parts.unshift(head);
      out = parts.concat(tail).join(",");
    }
    return (neg ? "-₹" : "₹") + out + "." + f;
  };
  const compact = (v) => {
    const a = Math.abs(v);
    if (a >= 1e7) return "₹" + (v / 1e7).toFixed(2) + " Cr";
    if (a >= 1e5) return "₹" + (v / 1e5).toFixed(2) + " L";
    return money(v);
  };
  const signed = (v) => (v >= 0 ? "+" : "") + money(v);
  const atBottom = () => scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 90;
  const toBottom = () => { scroll.scrollTop = scroll.scrollHeight; };

  /* ------------------------------- cards ------------------------------- */
  const head = (title, sub) => {
    const h = el("div", "card-head");
    h.appendChild(el("div", "t", title));
    if (sub) h.appendChild(el("div", "s", sub));
    return h;
  };
  const kv = (k, v) => {
    const r = el("div", "kv");
    r.appendChild(el("span", "k", k));
    r.appendChild(el("span", "v", v));
    return r;
  };
  const stat = (k, v, cls) => {
    const s = el("div", "stat");
    s.appendChild(el("div", "k", k));
    const val = el("div", "v" + (cls ? " " + cls : ""), v);
    s.appendChild(val);
    return s;
  };

  const RENDER = {
    portfolio(d) {
      const c = el("div", "card");
      c.appendChild(head(d.name, "Portfolio summary"));
      const b = el("div", "card-body");
      const grid = el("div", "split");
      grid.appendChild(stat("Current value", compact(d.totals.value)));
      grid.appendChild(stat(
        (d.totals.pnl >= 0 ? "Gain" : "Loss"),
        compact(d.totals.pnl) + " (" + d.totals.pnl_pct.toFixed(2) + "%)",
        d.totals.pnl >= 0 ? "up" : "down"));
      b.appendChild(grid);
      b.appendChild(kv("Invested", money(d.totals.invested)));
      b.appendChild(kv("Wallet", money(d.wallet_balance)));
      c.appendChild(b);

      if (d.holdings.length) {
        const l = el("div", "list");
        d.holdings.forEach((h) => {
          const it = el("div", "item");
          const left = el("div");
          left.appendChild(el("div", "n", h.name));
          left.appendChild(el("div", "m", h.qty + " qty · avg " + money(h.avg_price)));
          const right = el("div", "r");
          right.appendChild(el("div", "a", money(h.value)));
          right.appendChild(el("div", "b " + (h.pnl >= 0 ? "up" : "down"),
            signed(h.pnl) + " (" + h.pnl_pct.toFixed(1) + "%)"));
          it.append(left, right); l.appendChild(it);
        });
        c.appendChild(l);
      }
      if (d.sips.length) {
        const l = el("div", "list");
        d.sips.forEach((s) => {
          const it = el("div", "item");
          const left = el("div");
          left.appendChild(el("div", "n", s.scheme));
          left.appendChild(el("div", "m",
            money(s.amount) + "/" + s.frequency.replace("ly", "") +
            " · next " + s.next_debit));
          const right = el("div", "r");
          right.appendChild(el("div", "a", money(s.current_value)));
          const pill = el("span", "pill " + (s.status === "active" ? "ok" : "warn"), s.status);
          right.appendChild(pill);
          it.append(left, right); l.appendChild(it);
        });
        c.appendChild(l);
      }
      return c;
    },

    order_status(d) {
      const c = el("div", "card");
      c.appendChild(head(d.order_id + " · " + d.type,
        d.scheme || (money(d.amount) + " · placed " + d.placed_on)));
      const b = el("div", "card-body");
      const cls = d.status_code === "failed" ? "bad"
                : d.status_code === "units_pending" ? "warn" : "ok";
      b.appendChild(el("span", "pill " + cls, d.headline));

      const ul = el("ul", "steps");
      d.steps.forEach((s) => {
        const li = el("li", "step " + s.state);
        const rail = el("div", "rail");
        const dot = el("div", "dot");
        if (s.state === "done") dot.innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 6 9 17l-5-5"/></svg>';
        if (s.state === "failed") dot.innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M18 6 6 18M6 6l12 12"/></svg>';
        rail.appendChild(dot); rail.appendChild(el("div", "bar"));
        const txt = el("div", "txt");
        txt.appendChild(el("b", null, s.label));
        if (s.at) txt.appendChild(el("span", null, s.at));
        li.append(rail, txt); ul.appendChild(li);
      });
      b.appendChild(ul);
      if (d.detail) b.appendChild(el("div", "sub", d.detail));
      if (d.utr) b.appendChild(kv("Bank reference (UTR)", d.utr));
      c.appendChild(b);
      return c;
    },

    sip_projection(d) {
      const c = el("div", "card");
      c.appendChild(head("SIP illustration",
        money(d.sip_amount) + "/month · " + d.tenure_years + "y · " + d.expected_rate + "% assumed"));
      const b = el("div", "card-body");
      const grid = el("div", "split");
      grid.appendChild(stat("You invest", compact(d.invested)));
      grid.appendChild(stat("Illustrated value", compact(d.future_value), "up"));
      b.appendChild(grid);

      if (d.series.length > 1) {
        const max = d.series[d.series.length - 1].value || 1;
        const bars = el("div", "bars");
        d.series.forEach((p) => {
          const col = el("div", "b");
          const gain = Math.max(p.value - p.invested, 0);
          const g = el("div", "g"); g.style.height = (gain / max * 62) + "px";
          const pr = el("div", "p"); pr.style.height = (p.invested / max * 62) + "px";
          col.append(g, pr);
          col.title = "Year " + p.year + " · " + compact(p.value);
          bars.appendChild(col);
        });
        b.appendChild(bars);
        const lg = el("div", "legend");
        const a = el("span"); a.innerHTML = '<i style="background:#cdd8d4"></i>invested';
        const z = el("span"); z.innerHTML = '<i style="background:var(--accent)"></i>growth';
        lg.append(a, z); b.appendChild(lg);
      }
      b.appendChild(kv("Illustrated growth", signed(d.gain)));
      b.appendChild(el("div", "sub", d.disclaimer));
      c.appendChild(b);
      return c;
    },

    ticket(d) {
      const c = el("div", "card ticket");
      c.appendChild(head("Ticket " + d.ticket_id, d.category + " · " + d.team));
      const b = el("div", "card-body");
      const grid = el("div", "split");
      grid.appendChild(stat("Priority", d.priority));
      grid.appendChild(stat("First update", "≤ " + d.sla_hours + "h"));
      b.appendChild(grid);
      const m = el("div", "meter" + (d.priority_score >= 85 ? " hot" : ""));
      const fill = el("i"); fill.style.width = d.priority_score + "%";
      m.appendChild(fill);
      b.appendChild(el("div", "sub", "Priority score " + d.priority_score + "/100"));
      b.appendChild(m);
      if (d.order_id) b.appendChild(kv("Linked order", d.order_id));
      b.appendChild(kv("Raised for", d.raised_for));
      if (d.summary) b.appendChild(el("div", "sub", "“" + d.summary + "”"));
      c.appendChild(b);
      return c;
    },

    disclaimer(d) {
      const c = el("div", "card notice");
      const b = el("div", "card-body");
      b.appendChild(el("div", "t", d.title));
      b.appendChild(el("p", null, d.body));
      if (d.alternatives && d.alternatives.length) {
        const ul = el("ul");
        d.alternatives.forEach((a) => ul.appendChild(el("li", null, a)));
        b.appendChild(ul);
      }
      c.appendChild(b);
      return c;
    },
  };

  /* ------------------------------ thread ------------------------------- */
  function addUser(text) {
    const row = el("div", "row me");
    row.appendChild(el("div", "bubble", text));
    thread.appendChild(row); toBottom();
  }

  function addBot() {
    const row = el("div", "row bot");
    const bubble = el("div", "bubble");
    const dots = el("span", "typing");
    dots.innerHTML = "<i></i><i></i><i></i>";
    bubble.appendChild(dots);
    row.appendChild(bubble);
    thread.appendChild(row); toBottom();
    return { row, bubble, dots, started: false };
  }

  function renderCard(row, card) {
    const fn = RENDER[card.kind];
    if (!fn) return;                     // unknown kind: skip, never crash
    const holder = el("div");
    holder.style.maxWidth = "92%";
    holder.appendChild(fn(card.data));
    holder.className = "";
    const wrapRow = el("div", "row bot");
    wrapRow.appendChild(holder);
    thread.appendChild(wrapRow);
    if (atBottom()) toBottom();
  }

  function setChips(list) {
    chipBar.innerHTML = "";
    (list || []).forEach((c, i) => {
      const b = el("button", "chip", c.label);
      b.style.animationDelay = (i * 40) + "ms";
      b.addEventListener("click", () => { if (!busy) submit(c.send); });
      chipBar.appendChild(b);
    });
  }

  /* ------------------------------ network ------------------------------ */
  async function submit(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    busy = true; send.disabled = true; input.value = ""; setChips([]);
    addUser(text);
    const slot = addBot();

    let res;
    try {
      res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
    } catch (e) {
      slot.bubble.textContent = "I couldn't reach the server. Is it still running?";
      busy = false; send.disabled = false; return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const handle = (evt) => {
      if (evt.type === "session") {
        sessionId = evt.session_id; localStorage.setItem("sid", sessionId);
      } else if (evt.type === "token") {
        if (!slot.started) { slot.bubble.textContent = ""; slot.started = true; }
        slot.bubble.textContent += (slot.bubble.textContent ? " " : "") + evt.v;
        if (atBottom()) toBottom();
      } else if (evt.type === "card") {
        renderCard(slot.row, evt.card);
      } else if (evt.type === "chips") {
        setChips(evt.chips);
      }
    };

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        try { handle(JSON.parse(line)); } catch (_) { /* partial line */ }
      }
    }
    if (!slot.started) slot.bubble.textContent = "Sorry, I didn't catch that.";
    busy = false; send.disabled = false; input.focus(); toBottom();
  }

  /* ------------------------------ flyouts ------------------------------ */
  /* Header navigation. An item with `send` opens the chat and asks the
     assistant; an item without one is marked inert and styled as such,
     because a nav full of links that quietly do nothing is worse than a nav
     that admits which parts are wired up. */
  const I = {
    stocks: '<path d="M3 17l6-6 4 4 7-7M14 8h7v7"/>',
    funds: '<path d="M3 3v18h18M7 15l4-4 3 3 5-6"/>',
    sip: '<path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    calc: '<path d="M5 2h14v20H5zM9 6h6M9 11h.01M12 11h.01M15 11h.01M9 15h.01M12 15h.01M15 15h6"/>',
    wallet: '<path d="M3 7h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7zm0 0a2 2 0 0 1 2-2h11M17 13h.01"/>',
    doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h4"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    alert: '<path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
    star: '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
    search: '<path d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3"/>',
    gold: '<path d="M12 2 2 8l10 6 10-6-10-6zM2 16l10 6 10-6M2 12l10 6 10-6"/>',
    bank: '<path d="M3 21h18M4 10h16M5 10V7l7-4 7 4v3M6 21V10M10 21V10M14 21V10M18 21V10"/>',
    grow: '<path d="M3 17l6-6 4 4 7-7M14 8h7v7"/>',
    pnl: '<path d="M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H7"/>',
  };

  const MENUS = {
    investments: [{
      title: "Invest in",
      items: [
        { i: I.stocks, t: "Stocks", d: "Equity, ETFs and indices", send: "Show my portfolio" },
        { i: I.funds, t: "Mutual funds", d: "SIPs and lumpsum", send: "What is the status of my SIP?" },
        { i: I.calc, t: "SIP calculator", d: "Illustrate a monthly plan", send: "Calculate a SIP of 5000 for 10 years at 12%" },
      ],
    }, {
      title: "Also available",
      items: [
        { i: I.grow, t: "F&O", d: "Futures and options" },
        { i: I.gold, t: "Gold", d: "Digital gold" },
        { i: I.bank, t: "Fixed deposits", d: "Partner banks" },
        { i: I.star, t: "US stocks", d: "Invest overseas" },
      ],
    }],

    dashboard: [{
      title: "Your account",
      items: [
        { i: I.grow, t: "Overview", d: "Everything at a glance", send: "Show my portfolio" },
        { i: I.stocks, t: "Holdings", d: "Stocks you own", send: "What are my holdings?" },
        { i: I.pnl, t: "P&L and tax", d: "Gains and STCG", send: "Explain my P&L and STCG" },
        { i: I.wallet, t: "Wallet", d: "Available balance", send: "What is my wallet balance?" },
      ],
    }, {
      title: "Documents",
      items: [
        { i: I.doc, t: "Reports & statements", d: "Capital gains, holdings" },
        { i: I.doc, t: "Tax P&L statement", d: "For filing" },
      ],
    }],

    stocks: [{
      title: "Explore",
      items: [
        { i: I.search, t: "All stocks", d: "Browse the market" },
        { i: I.grow, t: "Top gainers & losers", d: "Today's movers" },
        { i: I.list, t: "Most traded", d: "By volume" },
        { i: I.star, t: "Watchlist", d: "Stocks you follow" },
      ],
    }, {
      title: "Your stocks",
      items: [
        { i: I.stocks, t: "My holdings", d: "Quantity, average, P&L", send: "What are my holdings?" },
        { i: I.pnl, t: "Profit & loss", d: "Realised and unrealised", send: "Explain my P&L and STCG" },
        { i: I.list, t: "Stock orders", d: "Placed and executed", send: "Show my recent orders" },
      ],
    }],

    funds: [{
      title: "Explore funds",
      items: [
        { i: I.search, t: "All mutual funds", d: "Browse every scheme" },
        { i: I.star, t: "Collections", d: "Large cap, ELSS, index" },
        { i: I.grow, t: "Fund comparison", d: "Side by side" },
      ],
    }, {
      title: "Your investments",
      items: [
        { i: I.sip, t: "My SIPs", d: "Active and paused", send: "What is the status of my SIP?" },
        { i: I.calc, t: "SIP calculator", d: "Illustrate a plan", send: "Calculate a SIP of 5000 for 10 years at 12%" },
        { i: I.doc, t: "Why T+2 allotment?", d: "When units appear", send: "Why does unit allotment take T+2 days?" },
      ],
    }],

    orders: [{
      title: "Order history",
      items: [
        { i: I.list, t: "All orders", d: "Everything on your account", send: "Show my recent orders" },
        { i: I.sip, t: "SIP instalments", d: "Debits and allotment", send: "What is the status of my SIP?" },
        { i: I.wallet, t: "Withdrawals", d: "Payouts to your bank", send: "Track my withdrawal" },
      ],
    }, {
      title: "Something wrong?",
      items: [
        { i: I.alert, t: "Failed payment", d: "Debited but not credited", send: "My deposit failed but money was debited" },
        { i: I.doc, t: "Raise a ticket", d: "Talk to a person", send: "I want to raise a ticket" },
      ],
    }],
  };

  const flyout = $("flyout"), scrim = $("scrim");
  const triggers = [...document.querySelectorAll(".navtrigger")];
  let openMenu = null;

  function closeMenu() {
    if (!openMenu) return;
    flyout.hidden = true; scrim.hidden = true; flyout.innerHTML = "";
    triggers.forEach((t) => t.setAttribute("aria-expanded", "false"));
    openMenu = null;
  }

  function openMenuFor(trigger) {
    const key = trigger.dataset.menu;
    if (openMenu === key) { closeMenu(); return; }
    closeMenu();

    const groups = MENUS[key];
    if (!groups) return;

    flyout.innerHTML = "";
    groups.forEach((group) => {
      const col = el("div", "fly-col");
      col.appendChild(el("h4", null, group.title));
      group.items.forEach((item) => {
        const wired = Boolean(item.send);
        const b = el("button", "fly-item" + (wired ? "" : " inert"));
        b.type = "button";
        b.setAttribute("role", "menuitem");
        if (!wired) b.setAttribute("aria-disabled", "true");

        const ico = el("span", "fly-ico");
        ico.innerHTML = '<svg viewBox="0 0 24 24">' + item.i + "</svg>";
        const txt = el("span");
        txt.appendChild(el("b", null, item.t));
        if (item.d) txt.appendChild(el("span", null, item.d));
        b.append(ico, txt);
        if (wired) b.appendChild(el("span", "fly-tag", "Ask"));

        if (wired) {
          b.addEventListener("click", () => {
            closeMenu();
            greeted = true;
            open(false);
            submit(item.send);
          });
        }
        col.appendChild(b);
      });
      flyout.appendChild(col);
    });

    flyout.hidden = false; scrim.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    openMenu = key;

    // Align under the trigger, nudged back inside the viewport if it would
    // overflow the right edge.
    const bar = document.querySelector(".topbar").getBoundingClientRect();
    const t = trigger.getBoundingClientRect();
    flyout.style.left = "0px";
    const width = flyout.offsetWidth;
    let left = t.left - bar.left;
    const maxLeft = bar.width - width - 16;
    if (left > maxLeft) left = Math.max(16, maxLeft);
    flyout.style.left = left + "px";
  }

  triggers.forEach((t) => {
    t.addEventListener("click", (e) => { e.stopPropagation(); openMenuFor(t); });
  });
  scrim.addEventListener("click", closeMenu);
  window.addEventListener("resize", closeMenu);

  /* ------------------------------- boot -------------------------------- */
  async function boot() {
    const url = "/api/session" + (sessionId ? "?session_id=" + encodeURIComponent(sessionId) : "");
    const s = await (await fetch(url)).json();
    sessionId = s.session_id; localStorage.setItem("sid", sessionId);
    who.textContent = s.user.name + " · " + s.user.persona;

    profileSel.innerHTML = "";
    s.profiles.forEach((p) => {
      const o = el("option", null, p.name + " — " + p.persona);
      o.value = p.user_id;
      if (p.user_id === s.user.user_id) o.selected = true;
      profileSel.appendChild(o);
    });

    thread.innerHTML = "";
    if (s.messages.length) {
      s.messages.forEach((m) => {
        if (m.role === "user") { addUser(m.text); return; }
        const row = el("div", "row bot");
        row.appendChild(el("div", "bubble", m.text));
        thread.appendChild(row);
        (m.cards || []).forEach((c) => renderCard(row, c));
      });
      greeted = true;
    }
    setChips(s.chips);
    buildBackdrop(s.user);
  }

  const HINTS = [
    "What is the status of my SIP?",
    "Track order ORD-77190",
    "Should I buy Tata Motors?",
    "My deposit failed but money was debited",
    "SIP of 5000 for 15 years at 12%",
    "Explain my P&L and STCG",
  ];

  function buildBackdrop(user) {
    const hints = $("hints");
    hints.innerHTML = "";
    HINTS.forEach((h) => {
      const b = el("button", "hint", h);
      b.addEventListener("click", () => { greeted = true; open(false); submit(h); });
      hints.appendChild(b);
    });

    // A data read, not a chat turn - so it takes the user id directly and
    // follows the profile switch instead of defaulting to the first user.
    fetch("/api/portfolio?user_id=" + encodeURIComponent(user.user_id))
      .then((r) => r.json()).then((r) => {
      const card = r.card;
      const tiles = $("tiles");
      tiles.innerHTML = "";
      if (!card) return;
      const d = card.data;
      const add = (k, v, d2, cls) => {
        const t = el("div", "tile");
        t.appendChild(el("div", "k", k));
        t.appendChild(el("div", "v", v));
        if (d2) t.appendChild(el("div", "d " + (cls || ""), d2));
        tiles.appendChild(t);
      };
      add("Current value", compact(d.totals.value),
          signed(d.totals.pnl) + " (" + d.totals.pnl_pct.toFixed(2) + "%)",
          d.totals.pnl >= 0 ? "up" : "down");
      add("Invested", compact(d.totals.invested));
      add("Wallet", money(d.wallet_balance));
      add("Active SIPs", String(d.sips.filter((s) => s.status === "active").length),
          d.sips.length + " total");
    }).catch(() => {});
  }

  /* `withGreeting` is false when the user arrived by clicking a suggestion:
     the greeting would occupy the widget and the suggestion, submitted while
     the first request was still in flight, would be dropped silently. */
  function open(withGreeting = true) {
    widget.classList.remove("closed");
    launcher.classList.add("hidden", "seen");
    // Lets the page reserve the column the widget sits in, so content
    // reflows beside it rather than disappearing underneath.
    document.body.classList.add("chat-open");
    input.focus();
    if (withGreeting && !greeted) { greeted = true; submit("hi"); }
    toBottom();
  }
  function close() {
    widget.classList.add("closed");
    launcher.classList.remove("hidden");
    document.body.classList.remove("chat-open");
  }

  launcher.addEventListener("click", open);
  $("collapse").addEventListener("click", close);
  $("restart").addEventListener("click", async () => {
    await fetch("/api/session/reset", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, user_id: "" }),
    });
    thread.innerHTML = ""; greeted = false; setChips([]); submit("hi");
  });
  profileSel.addEventListener("change", async () => {
    const r = await fetch("/api/session/profile", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, user_id: profileSel.value }),
    });
    const s = await r.json();
    who.textContent = s.user.name + " · " + s.user.persona;
    thread.innerHTML = ""; greeted = false; setChips(s.chips);
    buildBackdrop(s.user);
    if (!widget.classList.contains("closed")) { greeted = true; submit("hi"); }
  });
  form.addEventListener("submit", (e) => { e.preventDefault(); submit(input.value); });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    // Innermost layer first: a flyout over the page, then the chat.
    if (openMenu) { closeMenu(); return; }
    if (!widget.classList.contains("closed")) close();
  });

  widget.classList.add("closed");
  boot();
})();
