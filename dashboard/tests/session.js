    <script type="text/javascript">
        (function() {
  const fn = function() {
    Bokeh.safely(function() {
      (function(root) {
        function embed_document(root) {
        const render_items = [{"docid":"d00761f3-1a94-4903-b303-12bf64c22a29","roots":{"p1968":"a13dfdbf-19b4-41de-98f1-4251281bd1f9","p2089":"b942c6c9-400a-4dcd-bf26-fb759997141f","p2349":"ef4c2de6-b611-4d9f-bc51-3b8237ecf610","p2141":"c390f586-2dde-42bf-bb70-f167236d59d1","p2173":"a0bb159f-829a-4d92-a8a6-ad744800f666","p1004":"fc86b57d-f4c6-42ea-9776-89e192e5df8a","p1444":"ec36612a-d13c-4e96-a707-079b33721215","p2408":"cd1feb3d-d6d3-4b77-8811-a929089db21d","p1486":"e7c214ef-cdbf-41a2-88fa-d5ab2219c16b","p1926":"c0478ff9-1143-49ab-b783-3e5426cb585e","p2409":"ec8fa845-ccc0-4aa0-871e-eb6b173786ba","p2211":"e54d6616-1969-45fd-85bf-b1bdd2c2447b","p2280":"a3859fe3-1e75-45e9-9dd4-b4e42014647e"},"root_ids":["p1968","p2089","p2349","p2141","p2173","p1004","p1444","p2408","p1486","p1926","p2409","p2211","p2280"]}];
        root.Bokeh.embed.embed_items(docs_json, render_items);
        }
        if (root.Bokeh !== undefined) {
          embed_document(root);
        } else {
          let attempts = 0;
          const timer = setInterval(function(root) {
            if (root.Bokeh !== undefined) {
              clearInterval(timer);
              embed_document(root);
            } else {
              attempts++;
              if (attempts > 100) {
                clearInterval(timer);
                console.log("Bokeh: ERROR: Unable to run BokehJS code because BokehJS library is missing");
              }
            }
          }, 10, root)
        }
      })(window);
    });
  };
  if (document.readyState != "loading") fn();
  else document.addEventListener("DOMContentLoaded", fn);
})();
    </script>
