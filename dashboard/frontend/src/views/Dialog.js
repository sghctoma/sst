var m = require("mithril")

var Dialog = {
  state: {
    isOpen: false,
    openDialog: function() { Dialog.state.isOpen = true; },
    closeDialog: function() { Dialog.state.isOpen = false; }
  },
  oncreate : function(vnode) {
    window.onclick = function(event) {
      if (event.target == vnode.dom) {
        if (vnode.attrs.onclose) {
          vnode.attrs.onclose()
        }
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
            if (vnode.attrs.onclose) {
              vnode.attrs.onclose()
            }
            Dialog.state.closeDialog()
          }
        }, "Close"),
        vnode.children,
      ])
    ])
  },
}

module.exports = Dialog
