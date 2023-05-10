var m = require("mithril")

module.exports = {
  view: (vnode) => {
    const error = vnode.attrs.validate(vnode.attrs.value)
    const name = vnode.attrs.name
    return m(".input-field", [
      m("label", { for: name }, name),
      m("input", {
        ...vnode.attrs,
        class: error && "input-error",
      }),
      error && m(".error-message", error),
    ]);
  },
}
