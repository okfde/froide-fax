(function(){
  function setupSignatureWidgets() {
    var signatureWidgets = document.querySelectorAll('[data-signaturewidget]')
    for (var i = 0; i < signatureWidgets.length; i += 1) {
      setupSignatureWidget(signatureWidgets[i])
    }
  }

  function setupSignatureWidget(wrapper) {
    var clearButton = wrapper.querySelector("[data-action=clear]");
    var undoButton = wrapper.querySelector("[data-action=undo]");
    var formField = wrapper.querySelector("input[type=hidden]");
    var required = formField.required
    var form = findForm(formField)
    var submitButton = form.querySelector('button[type=submit]')

    var storedValue = formField.value
    var changed = false
  
    var canvas = wrapper.querySelector("canvas");
    
    var signaturePad = new SignaturePad(canvas, {
      backgroundColor: 'rgb(255, 255, 255)',
      minWidth: 1,
      maxWidth: 4,
      onEnd: function() {
        changed = true
        submitButton.disabled = false
        formField.value = signaturePad.toDataURL()
      }
    });

    function clear () {
      signaturePad.clear();
      formField.value = ''
      if (required) {
        submitButton.disabled = true
      }
    }

    clearButton.addEventListener("click", function (event) {
      clear()
    });
    
    undoButton.addEventListener("click", function (event) {
      console.log('undo')
      var data = signaturePad.toData();
    
      if (data) {
        data.pop(); // remove the last dot or line
        signaturePad.fromData(data);
      }
      formField.value = signaturePad.toDataURL()
    });   

    function resizeCanvas(initial) {
      console.log('resize', initial)
      // When zoomed out to less than 100%, for some very strange reason,
      // some browsers report devicePixelRatio as less than 1
      // and only part of the canvas is cleared then.
      var ratio =  Math.max(window.devicePixelRatio || 1, 1);
    
      // This part causes the canvas to be cleared
      canvas.width = canvas.offsetWidth * ratio;
      canvas.height = canvas.offsetHeight * ratio;
      canvas.getContext("2d").scale(ratio, ratio);
    
      // This library does not listen for canvas changes, so after the canvas is automatically
      // cleared by the browser, SignaturePad#isEmpty might still return false, even though the
      // canvas looks empty, because the internal data of this library wasn't cleared. To make sure
      // that the state of this library is consistent with visual state of the canvas, you
      // have to clear it manually.
      signaturePad.clear();
      if (!initial) {
        clear()
      }
      if (storedValue.length > 0 && !changed) {
        signaturePad.fromDataURL(storedValue)
      } else if (required) {
        submitButton.disabled = true
      }
    }

    window.addEventListener("orientationchange", resizeCanvas, false);
    resizeCanvas(true);

    if (storedValue.length > 0) {
      signaturePad.fromDataURL(storedValue)
    }
  }

  function findForm (el) {
    while (el !== null && el.tagName != 'FORM') {
      el = el.parentNode
    }
    return el
  }

  function ready(fn) {
    console.log('ready')
    if (document.attachEvent ? document.readyState === "complete" : document.readyState !== "loading"){
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  ready(setupSignatureWidgets)
}())
