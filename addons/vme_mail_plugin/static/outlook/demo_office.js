/* Stand-in for office.js in the browser preview (taskpane.html?demo=1).
 *
 * Implements only what taskpane.js uses, on top of the fictitious mails of ai/inbox/ (served by
 * /vme_mail_plugin/demo/inbox for an administrator). The task pane code is the same as in Outlook;
 * the login runs through the real mail_plugin flow in a popup window. "Antwoord invoegen" shows what
 * Outlook's reply window would contain: nothing is sent, here or in Outlook.
 */
(function () {
    "use strict";

    var mails = [];
    var itemChangedHandler = null;
    var params = new URLSearchParams(window.location.search);

    function toItem(mail) {
        return {
            from: mail.from,
            subject: mail.subject,
            internetMessageId: mail.internetMessageId,
            dateTimeCreated: mail.date,
            attachments: mail.attachments.map(function (att, index) {
                return { id: String(index), name: att.name, contentType: att.mimetype, isInline: false, attachmentType: "file" };
            }),
            body: {
                getAsync: function (coercion, callback) { callback({ status: "succeeded", value: mail.body }); },
            },
            getAttachmentContentAsync: function (id, callback) {
                callback({ status: "succeeded", value: { format: "base64", content: mail.attachments[Number(id)].datas } });
            },
            displayReplyForm: function (data) { showReplyWindow(mail, data.htmlBody || ""); },
        };
    }

    function showReplyWindow(mail, html) {
        var overlay = document.createElement("div");
        overlay.className = "demo-reply";
        overlay.innerHTML =
            '<div class="demo-reply-window" role="dialog" aria-label="Antwoordvenster">' +
            '<p class="muted">Zo opent Outlook het antwoordvenster. Er is niets verstuurd: de medewerker kijkt het ' +
            'antwoord na en drukt zelf op Verzenden.</p>' +
            "<p><b>Aan:</b> <span data-f='to'></span><br><b>Onderwerp:</b> <span data-f='subject'></span></p>" +
            '<div class="reply" data-f="body"></div>' +
            '<button class="primary" type="button">Sluiten (niet verzenden)</button></div>';
        overlay.querySelector("[data-f=to]").textContent = mail.from.displayName + " <" + mail.from.emailAddress + ">";
        overlay.querySelector("[data-f=subject]").textContent = "RE: " + mail.subject;
        // The html was built by taskpane.js from escaped text.
        overlay.querySelector("[data-f=body]").innerHTML = html;
        overlay.querySelector("button").onclick = function () { overlay.remove(); };
        document.body.appendChild(overlay);
    }

    function displayDialogAsync(url, options, callback) {
        var popup = window.open(url, "vme_outlook_auth", "width=520,height=680");
        var handlers = {};
        function onMessage(event) {
            if (event.origin !== window.location.origin || !event.data || !event.data.vmeAuth) return;
            window.removeEventListener("message", onMessage);
            if (handlers.dialogMessageReceived) handlers.dialogMessageReceived({ message: event.data.vmeAuth });
        }
        window.addEventListener("message", onMessage);
        callback(popup ? {
            status: "succeeded",
            value: {
                addEventHandler: function (type, handler) { handlers[type] = handler; },
                close: function () { if (!popup.closed) popup.close(); },
            },
        } : { status: "failed", error: { message: "De browser blokkeerde het venster." } });
    }

    function selectMail(index) {
        Office.context.mailbox.item = mails[index] ? toItem(mails[index]) : null;
        if (itemChangedHandler) itemChangedHandler();
    }

    function loadInbox() {
        return fetch("/vme_mail_plugin/demo/inbox", {
            method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin",
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", id: 1, params: {} }),
        }).then(function (r) { return r.json(); }).then(function (data) {
            if (data.error) throw new Error(data.error.data && data.error.data.message || data.error.message);
            return data.result.mails;
        });
    }

    window.Office = {
        isVmeDemo: true,
        CoercionType: { Text: "text" },
        AsyncResultStatus: { Succeeded: "succeeded", Failed: "failed" },
        EventType: { ItemChanged: "olkItemSelectedChanged", DialogMessageReceived: "dialogMessageReceived" },
        context: {
            displayLanguage: params.get("lang") || "nl-BE",
            requirements: { isSetSupported: function () { return true; } },
            ui: {
                displayDialogAsync: displayDialogAsync,
                openBrowserWindow: function (url) { window.open(url, "_blank", "noopener"); },
            },
            mailbox: {
                item: null,
                addHandlerAsync: function (type, handler) { itemChangedHandler = handler; },
            },
        },
        onReady: function (callback) {
            var bar = document.getElementById("demo-bar");
            var select = document.getElementById("demo-mail");
            bar.hidden = false;
            loadInbox().then(function (list) {
                mails = list;
                list.forEach(function (mail, index) {
                    var option = document.createElement("option");
                    option.value = index;
                    option.textContent = mail.file + " · " + mail.from.displayName + " · " + mail.subject;
                    select.appendChild(option);
                });
                var start = Math.max(0, list.findIndex(function (m) { return m.file === params.get("mail"); }));
                select.value = start;
                select.onchange = function () { selectMail(Number(select.value)); };
                Office.context.mailbox.item = list[start] ? toItem(list[start]) : null;
                callback({ host: "Outlook" });
            }).catch(function (error) {
                var app = document.getElementById("app");
                app.textContent = "";
                var p = document.createElement("p");
                p.className = "status error";
                p.textContent = "De voorbeeldmails laden lukt niet (" + error.message + "). Log eerst in Odoo in als beheerder: ";
                var a = document.createElement("a");
                a.href = "/web/login?redirect=" + encodeURIComponent(window.location.pathname + window.location.search);
                a.textContent = "inloggen";
                p.appendChild(a);
                app.appendChild(p);
            });
        },
    };
})();
