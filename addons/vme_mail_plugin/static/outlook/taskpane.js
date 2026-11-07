/* Task pane of the Outlook add-in (plain JavaScript, no build step).
 *
 * Reads the open mail, asks this Odoo which VME, lot and owner it belongs to, and shows what is open
 * and the AI proposal. Nothing is ever sent from here: "Antwoord invoegen" opens Outlook's own reply
 * window with the draft, and the staff member presses Send. The routes are in
 * controllers/mail_plugin.py; the login is mail_plugin's API key (scope outlook).
 */
(function () {
    "use strict";

    var ORIGIN = window.location.origin;
    var TOKEN_KEY = "vme_outlook_token";
    var DEMO = window.Office && Office.isVmeDemo === true;
    var strings = {};
    var state = { mail: null, context: null, matchIndex: 0, busy: false };

    // Texts: one JSON file per language in i18n/ (nl now, fr later)

    function t(key, values) {
        var text = strings[key] || key;
        Object.keys(values || {}).forEach(function (name) {
            text = text.split("{" + name + "}").join(values[name]);
        });
        return text;
    }

    function loadStrings() {
        var lang = ((Office.context && Office.context.displayLanguage) || navigator.language || "nl").slice(0, 2);
        var file = lang === "fr" ? "fr" : "nl";
        return fetch("i18n/" + file + ".json" + (window.VME_ASSET_VERSION || "")).then(function (r) { return r.json(); }).then(function (data) {
            strings = data;
            document.documentElement.lang = file;
            document.querySelectorAll("[data-t]").forEach(function (el) { el.textContent = t(el.dataset.t); });
        });
    }

    // Small DOM helper: el("p", {class: "muted"}, "text", child, ...)

    function el(tag, attrs) {
        var node = document.createElement(tag);
        Object.keys(attrs || {}).forEach(function (name) {
            var value = attrs[name];
            if (name === "onclick" || name === "onchange" || name === "onsubmit") node[name] = value;
            else if (value !== false && value !== null && value !== undefined) node.setAttribute(name, value === true ? "" : value);
        });
        Array.prototype.slice.call(arguments, 2).forEach(function add(child) {
            if (child === null || child === undefined || child === false) return;
            if (Array.isArray(child)) return child.forEach(add);
            node.appendChild(typeof child === "string" || typeof child === "number" ? document.createTextNode(String(child)) : child);
        });
        return node;
    }

    function render() {
        var app = document.getElementById("app");
        app.textContent = "";
        Array.prototype.slice.call(arguments).forEach(function (node) { if (node) app.appendChild(node); });
    }

    function status(message, kind) {
        var box = document.getElementById("status");
        if (!box) return;
        box.className = "status " + (kind || "info");
        box.textContent = message || "";
        box.hidden = !message;
    }

    // Login: mail_plugin's flow, an auth code in a dialog exchanged for an API key

    function getToken() {
        try { return window.localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
    }

    function setToken(token) {
        try {
            if (token) window.localStorage.setItem(TOKEN_KEY, token);
            else window.localStorage.removeItem(TOKEN_KEY);
        } catch (e) { /* private window: the user connects again next time */ }
    }

    function post(route, params, token) {
        var headers = { "Content-Type": "application/json" };
        if (token) headers.Authorization = "Bearer " + token;
        return fetch(ORIGIN + route, {
            method: "POST", headers: headers, credentials: "omit",
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", id: Date.now(), params: params || {} }),
        }).then(function (response) {
            return response.text().then(function (text) {
                var data;
                try { data = JSON.parse(text); } catch (e) {
                    throw { auth: response.status === 400 || response.status === 401, message: t("error.server") };
                }
                if (data.error) {
                    var message = (data.error.data && data.error.data.message) || data.error.message || "";
                    throw { auth: /access token/i.test(message), message: message };
                }
                return data.result;
            });
        });
    }

    function rpc(route, params) {
        return post(route, params, getToken()).catch(function (error) {
            if (error && error.auth) {
                setToken(null);
                showConnect(t("connect.expired"));
            }
            throw error;
        });
    }

    function showConnect(message) {
        render(
            el("section", { class: "card" },
                el("h2", {}, t("connect.title")),
                el("p", {}, t("connect.text")),
                message ? el("p", { class: "status warning" }, message) : null,
                el("button", { class: "primary", onclick: connect }, t("connect.button"))),
            el("p", { id: "status", class: "status", hidden: true }));
    }

    function connect() {
        var redirect = ORIGIN + "/vme_mail_plugin/static/outlook/auth_done.html" + (DEMO ? "?demo=1" : "");
        var url = ORIGIN + "/mail_plugin/auth?" + new URLSearchParams({
            scope: "outlook", friendlyname: "Outlook (VME)", redirect: redirect,
        }).toString();
        Office.context.ui.displayDialogAsync(url, { height: 70, width: 40, promptBeforeOpen: false }, function (result) {
            if (result.status !== Office.AsyncResultStatus.Succeeded) {
                status(t("connect.failed") + " " + (result.error && result.error.message || ""), "error");
                return;
            }
            var dialog = result.value;
            dialog.addEventHandler(Office.EventType.DialogMessageReceived, function (arg) {
                dialog.close();
                var answer = {};
                try { answer = JSON.parse(arg.message); } catch (e) { /* treated as refused */ }
                if (!answer.success || !answer.auth_code) {
                    showConnect(t("connect.refused"));
                    return;
                }
                post("/mail_plugin/auth/access_token", { auth_code: answer.auth_code }).then(function (result) {
                    if (!result || !result.access_token) throw { message: (result && result.error) || t("connect.failed") };
                    setToken(result.access_token);
                    refresh();
                }).catch(function (error) { showConnect(error.message); });
            });
        });
    }

    // The open mail

    function readMail() {
        var item = Office.context.mailbox && Office.context.mailbox.item;
        if (!item) return Promise.resolve(null);
        return new Promise(function (resolve) {
            item.body.getAsync(Office.CoercionType.Text, function (result) {
                var created = item.dateTimeCreated;
                resolve({
                    email: (item.from && item.from.emailAddress) || "",
                    name: (item.from && item.from.displayName) || "",
                    subject: item.subject || "",
                    messageId: item.internetMessageId || "",
                    date: created && created.toLocaleString ? created.toLocaleString() : (created || ""),
                    body: result.status === Office.AsyncResultStatus.Succeeded ? result.value : "",
                    attachments: (item.attachments || []).filter(function (a) {
                        return !a.isInline && (!a.attachmentType || a.attachmentType === "file");
                    }),
                });
            });
        });
    }

    function attachmentContents(mail) {
        // Content of the attachments needs Mailbox 1.8; without it the mail is filed without them.
        var item = Office.context.mailbox.item;
        var supported = Office.context.requirements && Office.context.requirements.isSetSupported("Mailbox", "1.8");
        if (!supported || !item.getAttachmentContentAsync || !mail.attachments.length) return Promise.resolve([]);
        return Promise.all(mail.attachments.map(function (att) {
            return new Promise(function (resolve) {
                item.getAttachmentContentAsync(att.id, function (result) {
                    var ok = result.status === Office.AsyncResultStatus.Succeeded && result.value.format === "base64";
                    resolve(ok ? { name: att.name, mimetype: att.contentType, datas: result.value.content } : null);
                });
            });
        })).then(function (list) { return list.filter(Boolean); });
    }

    function refresh(choice) {
        if (!getToken()) {
            showConnect();
            return;
        }
        render(el("p", { class: "muted" }, t("loading")));
        readMail().then(function (mail) {
            state.mail = mail;
            if (!mail) {
                render(el("p", { class: "muted" }, t("no_mail")));
                return null;
            }
            var params = { email: mail.email, name: mail.name, subject: mail.subject, message_id: mail.messageId };
            if (choice) {
                params.association_id = choice.association_id;
                params.lot_id = choice.lot_id;
            }
            return rpc("/mail_plugin/vme/context", params).then(function (context) {
                state.context = context;
                state.matchIndex = 0;
                showContext();
            });
        }).catch(function (error) {
            if (error && error.auth) return;
            render(el("p", { class: "status error" }, (error && error.message) || t("error.server")),
                el("button", { onclick: function () { refresh(); } }, t("retry")));
        });
    }

    // The panel

    function showContext() {
        var context = state.context;
        var match = context.matches[state.matchIndex];
        render(
            senderLine(),
            context.matches.length > 1 ? matchChooser() : null,
            match ? matchCard(match) : unknownCard(),
            context.proposal ? proposalCard(context.proposal) : null,
            match ? openItemsCard(match) : null,
            actionsCard(match),
            el("p", { id: "status", class: "status", hidden: true }));
    }

    function senderLine() {
        var mail = state.mail;
        return el("p", { class: "sender" },
            el("strong", {}, mail.name || mail.email), mail.name ? " <" + mail.email + ">" : "",
            el("br"), el("span", { class: "muted" }, mail.subject));
    }

    function matchChooser() {
        var select = el("select", { id: "match", onchange: function (event) {
            state.matchIndex = Number(event.target.value);
            showContext();
        } });
        state.context.matches.forEach(function (match, index) {
            var label = match.vme.name + " - " + match.lots.map(function (l) { return l.name; }).join(", ") +
                " (" + t("role." + match.role) + ")";
            select.appendChild(el("option", { value: index, selected: index === state.matchIndex }, label));
        });
        return el("section", { class: "card" }, el("label", { for: "match" }, t("match.several")), select);
    }

    function link(label, url) {
        return el("a", { href: url, onclick: function (event) {
            event.preventDefault();
            openUrl(url);
        } }, label);
    }

    function openUrl(url) {
        if (Office.context.ui && Office.context.ui.openBrowserWindow) Office.context.ui.openBrowserWindow(url);
        else window.open(url, "_blank", "noopener");
    }

    function matchCard(match) {
        var lots = match.lots.map(function (lot) { return link(lot.name, lot.url); });
        var lotLine = el("span", {});
        lots.forEach(function (node, index) {
            if (index) lotLine.appendChild(document.createTextNode(", "));
            lotLine.appendChild(node);
        });
        var reason = match.role === "manual" ? t("match.reason_manual")
            : t("match.reason", { role: t("role." + match.role), name: match.partner.name });
        return el("section", { class: "card match" },
            el("h2", {}, link(match.vme.name, match.vme.url)),
            el("p", {},
                lots.length ? el("span", {}, t("match.lots", { count: lots.length }), " ", lotLine) : null,
                lots.length ? " · " : null,
                el("span", { class: "badge role-" + match.role }, t("role." + match.role))),
            match.partner ? el("p", {}, link(match.partner.name, match.partner.url)) : null,
            el("p", { class: "muted" }, reason),
            match.role === "manual" ? null : el("button", { class: "link", onclick: function () { showSearch(); } }, t("search.other")));
    }

    function unknownCard() {
        var proposal = state.context.proposal;
        return el("section", { class: "card" },
            el("h2", {}, t("unknown.title")),
            el("p", {}, t("unknown.text")),
            // The AI assistant already linked this mail (from its text): offer that link in one click.
            proposal && proposal.vme.id ? el("button", { class: "primary", onclick: function () {
                refresh({ association_id: proposal.vme.id, lot_id: proposal.lot_id || false });
            } }, t("unknown.use_proposal", { name: proposal.vme.name + (proposal.lot ? " - " + proposal.lot : "") })) : null,
            searchForm());
    }

    function searchForm() {
        var input = el("input", { type: "search", id: "search", placeholder: t("search.placeholder"), autocomplete: "off" });
        var results = el("ul", { class: "results" });
        var form = el("form", { onsubmit: function (event) {
            event.preventDefault();
            rpc("/mail_plugin/vme/search", { term: input.value }).then(function (answer) {
                results.textContent = "";
                if (!answer.results.length) results.appendChild(el("li", { class: "muted" }, t("search.none")));
                answer.results.forEach(function (result) {
                    results.appendChild(el("li", {}, el("button", { class: "link", onclick: function () {
                        refresh({ association_id: result.association_id, lot_id: result.lot_id });
                    } }, result.name)));
                });
            }).catch(function (error) { if (!error.auth) status(error.message, "error"); });
        } }, input, el("button", { type: "submit" }, t("search.button")));
        return el("div", {}, form, results);
    }

    function showSearch() {
        render(senderLine(), el("section", { class: "card" }, el("h2", {}, t("search.title")), searchForm()),
            el("button", { class: "link", onclick: function () { showContext(); } }, t("back")),
            el("p", { id: "status", class: "status", hidden: true }));
        document.getElementById("search").focus();
    }

    function htmlToText(html) {
        // The proposal arrives as sanitized HTML from Odoo; show and insert it as plain paragraphs.
        var doc = new DOMParser().parseFromString("<div>" + (html || "") + "</div>", "text/html");
        var blocks = Array.prototype.map.call(doc.body.firstChild.querySelectorAll("p"), function (p) {
            p.querySelectorAll("br").forEach(function (br) { br.replaceWith("\n"); });
            return p.textContent.trim();
        }).filter(Boolean);
        return blocks.length ? blocks : [doc.body.textContent.trim()].filter(Boolean);
    }

    function escapeHtml(text) {
        return text.replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
    }

    function proposalCard(proposal) {
        var blocks = htmlToText(proposal.reply_html);
        var reply = el("div", { class: "reply" });
        blocks.forEach(function (block) {
            var p = el("p");
            block.split("\n").forEach(function (line, index) {
                if (index) p.appendChild(el("br"));
                p.appendChild(document.createTextNode(line));
            });
            reply.appendChild(p);
        });
        return el("section", { class: "card proposal" },
            el("h2", {}, t("proposal.title"), " ", el("span", { class: "badge draft" }, t("proposal.not_sent"))),
            el("p", {}, link(proposal.record.name, proposal.record.url)),
            el("dl", {},
                proposal.topic ? el("dt", {}, t("proposal.topic")) : null, proposal.topic ? el("dd", {}, proposal.topic) : null,
                proposal.lot ? el("dt", {}, t("proposal.lot")) : null, proposal.lot ? el("dd", {}, proposal.vme.name + " - " + proposal.lot) : null,
                proposal.confidence ? el("dt", {}, t("proposal.confidence")) : null,
                proposal.confidence ? el("dd", {}, proposal.confidence + (proposal.reason ? " — " + proposal.reason : "")) : null),
            blocks.length ? el("details", { open: true }, el("summary", {}, proposal.reply_subject || t("proposal.reply")), reply)
                : el("p", { class: "muted" }, t("proposal.no_reply")),
            blocks.length ? el("button", { class: "primary", onclick: function () { insertReply(blocks); } }, t("action.reply")) : null);
    }

    function insertReply(blocks) {
        // Opens Outlook's reply window with the draft; the staff member checks it and presses Send.
        var html = blocks.map(function (block) {
            return "<p>" + escapeHtml(block).replace(/\n/g, "<br>") + "</p>";
        }).join("");
        Office.context.mailbox.item.displayReplyForm({ htmlBody: html });
        status(t("action.reply_done"), "info");
    }

    function formatDate(iso) {
        var parts = (iso || "").split("-");
        return parts.length === 3 ? parts[2] + "/" + parts[1] + "/" + parts[0] : iso;
    }

    function openItemsCard(match) {
        var items = match.open_items;
        var empty = !items.arrears.length && !items.requests.length && !items.claims.length;
        return el("section", { class: "card" },
            el("h2", {}, t("open.title")),
            empty ? el("p", { class: "muted" }, t("open.none")) : null,
            items.arrears.length ? el("div", {},
                el("h3", { class: "danger" }, t("open.arrears", { total: items.arrears_total })),
                el("ul", {}, items.arrears.map(function (line) {
                    return el("li", {}, line.name + " · " + line.amount_text + " · " +
                        t("open.due", { date: formatDate(line.date_due), days: line.days_overdue }) + (line.fund ? " · " + line.fund : ""));
                }))) : null,
            items.requests.length ? el("div", {}, el("h3", {}, t("open.requests")),
                el("ul", {}, items.requests.map(function (r) { return el("li", {}, link(r.name, r.url), " · " + r.state); }))) : null,
            items.claims.length ? el("div", {}, el("h3", {}, t("open.claims")),
                el("ul", {}, items.claims.map(function (c) { return el("li", {}, link(c.name, c.url), " · " + c.state); }))) : null);
    }

    function actionsCard(match) {
        if (!match) return null;
        var canWrite = state.context.can_write;
        // Where to file the mail: the VME, or one of its open requests and damage claims.
        var target = el("select", { id: "log-target" },
            el("option", { value: "vme.association:" + match.vme.id }, t("action.log_vme", { name: match.vme.name })));
        match.open_items.requests.forEach(function (r) { target.appendChild(el("option", { value: "vme.request:" + r.id }, r.name)); });
        match.open_items.claims.forEach(function (c) { target.appendChild(el("option", { value: "vme.damage.claim:" + c.id }, c.name)); });
        var types = el("select", { id: "request-type" });
        state.context.request_types.forEach(function (type) { types.appendChild(el("option", { value: type.code }, type.name)); });
        return el("section", { class: "card actions" },
            el("h2", {}, t("action.title")),
            canWrite ? null : el("p", { class: "status warning" }, t("action.read_only")),
            el("label", { for: "log-target" }, t("action.log_where")), target,
            el("button", { disabled: !canWrite, onclick: function (event) { logMail(event.target, target.value); } }, t("action.log")),
            el("label", { for: "request-type" }, t("action.request_type")), types,
            el("button", { disabled: !canWrite, onclick: function (event) { createRequest(event.target, match, types.value); } }, t("action.request")),
            el("p", { class: "muted small" }, t("action.nothing_sent")));
    }

    function withBusy(button, promise) {
        button.disabled = true;
        return promise.catch(function (error) {
            if (!error.auth) status((error && error.message) || t("error.server"), "error");
        }).then(function () { button.disabled = false; });
    }

    function logMail(button, target) {
        var parts = target.split(":");
        var mail = state.mail;
        withBusy(button, attachmentContents(mail).then(function (attachments) {
            return rpc("/mail_plugin/vme/log", {
                model: parts[0], res_id: Number(parts[1]), subject: mail.subject, email: mail.email, name: mail.name,
                body: mail.body, date: mail.date, attachments: attachments,
            });
        }).then(function (result) {
            var box = document.getElementById("status");
            status(t("action.log_done") + " ", "success");
            box.appendChild(link(t("action.open_odoo"), result.url));
        }));
    }

    function createRequest(button, match, requestType) {
        var mail = state.mail;
        withBusy(button, attachmentContents(mail).then(function (attachments) {
            return rpc("/mail_plugin/vme/request", {
                association_id: match.vme.id, request_type: requestType, email: mail.email, name: mail.name,
                lot_id: match.lots.length === 1 ? match.lots[0].id : false, subject: mail.subject, body: mail.body,
                message_id: mail.messageId, attachments: attachments,
            });
        }).then(function (result) {
            // Show the panel again with the new request among the open items, then the confirmation.
            var current = match.role === "manual"
                ? { association_id: match.vme.id, lot_id: match.lots.length ? match.lots[0].id : false } : null;
            var params = { email: mail.email, name: mail.name, subject: mail.subject, message_id: mail.messageId };
            if (current) Object.assign(params, current);
            var index = state.matchIndex;
            return rpc("/mail_plugin/vme/context", params).then(function (context) {
                state.context = context;
                state.matchIndex = Math.min(index, Math.max(context.matches.length - 1, 0));
                showContext();
                status(t("action.request_done", { name: result.name }) + " ", "success");
                document.getElementById("status").appendChild(link(t("action.open_odoo"), result.url));
            });
        }));
    }

    // Start

    Office.onReady(function () {
        loadStrings().then(function () {
            if (Office.context.mailbox && Office.context.mailbox.addHandlerAsync && Office.EventType.ItemChanged) {
                // A pinned pane follows the selected mail.
                Office.context.mailbox.addHandlerAsync(Office.EventType.ItemChanged, function () { refresh(); });
            }
            refresh();
        });
    });
})();
