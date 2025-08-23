window.drawBench = function(feature, latlng, context){
            console.log("DEBUG | drew bench:", feature.properties.id);
            // access the map from the context
            const map = context.layer && context.layer._map;
            // maybe has some safety effect?
            if (window.__lastSelectedBench === undefined) window.__lastSelectedBench = null;
            const id = feature && feature.properties && feature.properties.id;

            // bench icon depends on kiffen_erlaubt
            const kiffen_erlaubt = feature && feature.properties && feature.properties.kiffen_erlaubt;
            const iconUrl = id === window.__lastSelectedBench ? (kiffen_erlaubt ? "assets/bench_kiffen_selected.png" : "assets/bench_selected.png") : (kiffen_erlaubt ? "assets/bench_kiffen.png":"assets/bench.png");
            //const iconUrl = kiffen_erlaubt ? "assets/bench_kiffen.png" : "assets/bench.png";
            const flag = L.icon({
                iconUrl: iconUrl,
                iconSize: [48, 48],
                iconAnchor: [24, 48],
                popupAnchor: [0, -16]
            });
            const marker = L.marker(latlng, {icon: flag});

            // If this bench layer ever gets removed (e.g. filtered out), clean up extras if it was selected
            //when dl.GeoJSON updates and removes markers, every removed marker emits a "removed" signal
            marker.on("remove", function (e) {
                // if this removed marker was the selected one, clear everything
                if (window.__lastSelectedBench === id) {
                    // remove the extra overlay group if present
                    if (window.__selectedExtras) {
                        // try to get a map reference; fallback to the extras' map
                        const map = e.target._map || (window.__selectedExtras && window.__selectedExtras._map);
                        if (map) map.removeLayer(window.__selectedExtras);
                    }
                    window.__selectedExtras = null;
                    window.__lastSelectedMarker = null;
                    window.__lastSelectedBench = null;
                }

                // also handle the case where we were tracking this marker but it’s no longer the selected one
                if (window.__lastSelectedMarker === marker) {
                    window.__lastSelectedMarker = null;
                }
        });

            const propsAll = feature.properties || {};
            const benchLatLng = [latlng.lat, latlng.lng];

            // prepare "children" layer group for this bench
            const children = [];

            if (propsAll.toilet_lat && propsAll.toilet_lon){
                const toiletLatLng = [propsAll.toilet_lat, propsAll.toilet_lon];
                const toiletIcon = L.icon({
                    iconUrl:"assets/toilet.png",
                    iconSize: [48,48],
                    iconAnchor:[24,48]
                });
                const toiletMarker = L.marker(toiletLatLng, {icon: toiletIcon});

                const toiletLine = L.polyline([benchLatLng, toiletLatLng], {color:"black", weight:1});

                // invisible midpoint marker with tooltip
                const toiletDistance = L.circleMarker(
                    [(benchLatLng[0]+toiletLatLng[0])/2,(benchLatLng[1]+toiletLatLng[1])/2],
                    {radius:0.1, opacity:0, fillOpacity:0}
                ).bindTooltip(Math.round(propsAll.toilet_dist) + " m", {
                    permanent:true, 
                    direction:"center", 
                    className:"distance-label"
                });

                // adds these element to the children array (or list?)
                children.push(toiletMarker, toiletLine, toiletDistance);
            }

            if (propsAll.shop_lat && propsAll.shop_lon){
                const shopLatLng = [propsAll.shop_lat, propsAll.shop_lon];
                const shopIcon = L.icon({
                    iconUrl:"assets/shop.png",
                    iconSize: [48,48],
                    iconAnchor:[24,48]
                });
                const shopMarker = L.marker(shopLatLng, {icon: shopIcon});

                const shopLine = L.polyline([benchLatLng, shopLatLng], {color:"black", weight:1});

                // invisible midpoint marker with tooltip
                const shopDistance = L.circleMarker(
                    [(benchLatLng[0]+shopLatLng[0])/2,(benchLatLng[1]+shopLatLng[1])/2],
                    {radius:0.1, opacity:0, fillOpacity:0}
                ).bindTooltip(Math.round(propsAll.shop_dist) + " m", {
                    permanent:true, 
                    direction:"center", 
                    className:"distance-label"
                });
                
                //split shop_opening_hours into separate lines
                function createShopHours(opening_hours) {
                    if (typeof opening_hours !== "string") return "";

                    // Split on semicolon + optional space
                    const parts = opening_hours.split(/\s*;\s*/);

                    // Join them with <br> tags
                    return parts.join("<br>");
                }

                // construct shop tooltip
                let shopTooltip = "";
                if(propsAll.shop_name) shopTooltip += propsAll.shop_name;
                if(propsAll.shop_opening_hours) {
                    shopTooltip += "<br/>" + createShopHours(propsAll.shop_opening_hours);
                }
                if(shopTooltip) shopMarker.bindTooltip(shopTooltip, {permanent:true, direction:"bottom", className:"shop-label", offset:[0,0]});
                

                // adds these element to the children array (or list?)
                children.push(shopMarker, shopLine, shopDistance);
            }

            // Create bench link box to show on marker click
            window.__createBenchLink = function(feature){
                const existing = document.getElementById("bench-link-box");
                if(existing) existing.remove();

                const lat = feature._latlng.lat;
                const lon = feature._latlng.lng;
                const nav = lat && lon ? `https://www.google.com/maps/search/?api=1&query=${lat},${lon}` : "#";

                const outer = document.createElement("div");
                outer.id = "bench-link-box";

                const inner = document.createElement("a");
                inner.id = "bench-link-inner";
                inner.href = nav
                inner.target = "_blank";
                inner.innerText = "Bank in Google Maps öffnen";
                inner.style.pointerEvents = "auto";

                outer.appendChild(inner);
                document.body.appendChild(outer);
            }

            // Remove bench link box. Called when a bench is clicked twice
            window.__removeBenchLink = function(){
                const existing = document.getElementById("bench-link-box");
                if(existing) existing.remove();
            }

            // add a click handler to the bench marker
            // when the "click"-event (from Leaflet) of this marker fires, execute this function
            marker.on("click", function(e) {
                const map = e.target._map;  // ✅ guaranteed to exist here
                if (!map) return;

                if (window.__lastSelectedBench === id) {
                    window.__removeBenchLink();
                } else {
                    window.__createBenchLink(marker);
                }

                // SELECTION LOGIC. check if clicked id is the same as previously selected bench. If yes, set selected to null, if no set it to last clicked id
                window.__lastSelectedBench = (window.__lastSelectedBench === id) ? null : id;

                // ICON stuff
                // something about your logic is off. When you select a bench, filter and then unfilter, the previously selected bench stays selected even when you click other benches.
                // updates icon of previously selected marker depending on the icon it had before (feels hacky)
                if (window.__lastSelectedMarker) {
                    const prevMarker = window.__lastSelectedMarker;
                    const prevKiffen = prevMarker.options.icon.options.iconUrl.includes("kiffen");
                    prevMarker.setIcon(L.icon({
                        iconUrl: prevKiffen ? "assets/bench_kiffen.png" : "assets/bench.png",
                        iconSize: [48,48], iconAnchor: [24, 48], popupAnchor: [0, -16]
                    })
                    )
                }
                window.__lastSelectedMarker = marker;
                // updates the last clicked markers icon to reflect selection
                const newIconUrl = id === window.__lastSelectedBench ? (kiffen_erlaubt ? "assets/bench_kiffen_selected.png" : "assets/bench_selected.png") : (kiffen_erlaubt ? "assets/bench_kiffen.png":"assets/bench.png");
                marker.setIcon(L.icon({
                    iconUrl: newIconUrl,
                    iconSize: [48, 48],
                    iconAnchor: [24, 48],
                    popupAnchor: [0, -16]
                }));

                console.log("DEBUG | Clicked bench. Currently selected:", window.__lastSelectedBench)
                
                // remove previously shown extras
                if (window.__selectedExtras) {
                    map.removeLayer(window.__selectedExtras);
                }

                // add new ones if bench is selected
                if (children.length > 0 && id === window.__lastSelectedBench) {
                    window.__selectedExtras = L.layerGroup(children).addTo(map);
                } else {
                    window.__selectedExtras = null;
                }
                
                //context.layer.update();
            });

            return marker;
};
