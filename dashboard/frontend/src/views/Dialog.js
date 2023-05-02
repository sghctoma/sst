var m = require("mithril")

class Dialog {
  state = {
    isOpen: false,
    onopen: null,
    onclose: null,
    openDialog: () => {
      if (this.state.onopen) {
        this.state.onopen()
      }
      this.state.isOpen = true;
    },
    closeDialog: () => {
      if (this.state.onclose) {
        this.state.onclose()
      }
      this.state.isOpen = false;
    }
  }
  oncreate = (vnode) => {
    this.state.onopen = vnode.attrs.onopen
    this.state.onclose = vnode.attrs.onclose
  }
  view = (vnode) => {
    return m("div", {
      id: "modal",
      onclick: (event) => {
        if (event.target.id == "modal") {
          this.state.closeDialog()
          m.redraw();
        }
      },
      class: this.state.isOpen ? "modal modal-shown" : "modal modal-hidden"
    }, [
      m("div.modal-content", {style: "float: right;"}, [
        m(".modal-close", {
          onclick: () => {
            this.state.closeDialog()
          }
        }, "Close"),
        vnode.children,
      ])
    ])
  }
}

module.exports = Dialog
