var m = require("mithril")

module.exports = {
  view: (vnode) => {
    const { name, value, oninput, validate } = vnode.attrs
    const error = validate(value)
    return m(".input-field", [
      m("label", { for: name }, name),
      m("textarea", {
        name,
        value,
        oninput,
        rows: 10,
        class: error && "input-error",
      }),
      error && m(".error-message", error),
    ]);
  },
}
