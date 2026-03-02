/**
 * AÇÜ Chatbot - Sayfa içi widget
 * egemenulker.com gibi ana sitede sadece floating buton + açılır chat penceresi.
 * Tam sayfa chatbot: /chatbot
 *
 * Kullanım: <script src="https://egemenulker.com/chatbot/chatbot-widget.js"></script>
 * veya inline: <script> ... bu dosyanın içeriği ... </script>
 */
(function () {
  'use strict';

  var config = window.ACU_CHATBOT_WIDGET || {};
  var chatbotUrl = config.chatbotUrl || '/chatbot';
  var position = config.position || 'bottom-right'; // bottom-right | bottom-left
  var buttonLabel = config.buttonLabel || 'Chat';
  var zIndex = config.zIndex != null ? config.zIndex : 999999;

  var isOpen = false;
  var container, btn, panel, iframe, closeBtn;

  function createWidget() {
    container = document.createElement('div');
    container.id = 'acu-chatbot-widget';
    container.setAttribute('aria-label', 'AÇÜ Asistan sohbet');

    var style = document.createElement('style');
    style.textContent =
      '#acu-chatbot-widget{font-family:system-ui,-apple-system,sans-serif;position:fixed;z-index:' +
      zIndex +
      ';}' +
      '#acu-chatbot-widget .acu-w-btn{width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;' +
      'box-shadow:0 4px 12px rgba(0,0,0,.15);background:#0b2e17;color:#fff;font-size:14px;' +
      'display:flex;align-items:center;justify-content:center;transition:transform .2s;}' +
      '#acu-chatbot-widget .acu-w-btn:hover{transform:scale(1.05);}' +
      '#acu-chatbot-widget .acu-w-panel{display:none;position:fixed;width:100%;max-width:420px;' +
      'height:85vh;max-height:680px;bottom:72px;border-radius:12px;overflow:hidden;' +
      'box-shadow:0 8px 32px rgba(0,0,0,.2);background:#fff;}' +
      '#acu-chatbot-widget .acu-w-panel.acu-open{display:block;}' +
      '#acu-chatbot-widget.acu-pos-left .acu-w-panel{left:16px;right:auto;}' +
      '#acu-chatbot-widget.acu-pos-right .acu-w-panel{right:16px;left:auto;}' +
      '#acu-chatbot-widget.acu-pos-left .acu-w-btn{position:fixed;left:16px;bottom:16px;}' +
      '#acu-chatbot-widget.acu-pos-right .acu-w-btn{position:fixed;right:16px;bottom:16px;}' +
      '#acu-chatbot-widget .acu-w-panel iframe{width:100%;height:100%;border:none;}' +
      '#acu-chatbot-widget .acu-w-close{position:absolute;top:8px;right:8px;width:32px;height:32px;' +
      'border:none;border-radius:50%;background:rgba(0,0,0,.1);cursor:pointer;z-index:1;font-size:18px;line-height:1;}';

    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'acu-w-btn';
    btn.innerHTML = '💬';
    btn.setAttribute('aria-label', buttonLabel);
    btn.setAttribute('title', buttonLabel);

    panel = document.createElement('div');
    panel.className = 'acu-w-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Sohbet penceresi');

    iframe = document.createElement('iframe');
    iframe.title = 'AÇÜ Asistan sohbet';
    iframe.src = chatbotUrl;

    closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'acu-w-close';
    closeBtn.innerHTML = '×';
    closeBtn.setAttribute('aria-label', 'Kapat');

    panel.appendChild(closeBtn);
    panel.appendChild(iframe);
    container.appendChild(style);
    container.appendChild(panel);
    container.appendChild(btn);

    if (position === 'bottom-left') container.classList.add('acu-pos-left');
    else container.classList.add('acu-pos-right');

    function toggle() {
      isOpen = !isOpen;
      panel.classList.toggle('acu-open', isOpen);
      btn.setAttribute('aria-expanded', isOpen);
    }

    btn.addEventListener('click', toggle);
    closeBtn.addEventListener('click', toggle);

    document.body.appendChild(container);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createWidget);
  } else {
    createWidget();
  }
})();
