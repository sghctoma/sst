var m = require("mithril")

var SessionList = require("./views/SessionList")
var Layout = require("./views/Layout")
var Dashboard = require("./views/Dashboard")
var SST = require("./models/Global")

m.route.prefix = '#'
m.route(document.body, "/dashboard", {
    "/dashboard": {
        render: function() {
            return m(Layout, m(Dashboard, {key: "last"}))
        }
    },
    "/dashboard/:key": {
        render: function(vnode) {
            return m(Layout, m(Dashboard, vnode.attrs))
        }
    },
})

window.SST = SST
