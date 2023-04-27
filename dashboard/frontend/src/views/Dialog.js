var m = require("mithril")

var Dialog = {
  state: {
    isOpen: false,
    onopen: null,
    onclose: null,
    openDialog: function() {
      if (Dialog.state.onopen) {
        Dialog.state.onopen()
      }
      Dialog.state.isOpen = true;
    },
    closeDialog: function(vnode) {
      if (Dialog.state.onclose) {
        Dialog.state.onclose()
      }
      Dialog.state.isOpen = false;
    }
  },
  oncreate : function(vnode) {
    Dialog.state.onopen = vnode.attrs.onopen
    Dialog.state.onclose = vnode.attrs.onclose
    window.onclick = function(event) {
      if (event.target == vnode.dom) {
        Dialog.state.closeDialog();
        m.redraw();
      }
    }
  },
  view: function(vnode) {
    return m("div", {class: Dialog.state.isOpen ? "modal modal-shown" : "modal modal-hidden"}, [
      m("div.modal-content", [
        m(".modal-close", {
          onclick: () => {
            Dialog.state.closeDialog()
          }
        }, "Close"),
        vnode.children,
      ])
    ])
  },
}

module.exports = Dialog
