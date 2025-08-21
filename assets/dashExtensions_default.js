window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, latlng, index, context) {
            const scatterIcon = L.DivIcon.extend({
                createIcon: function(oldIcon) {
                    let icon = L.DivIcon.prototype.createIcon.call(this, oldIcon);
                    icon.style.backgroundColor = 'rgba(255,255,255,0.7)'; // fixed color
                    return icon;
                }
            });
            const icon = new scatterIcon({
                html: '<div><span>' + feature.properties.point_count_abbreviated + '</span></div>',
                className: "marker-cluster",
                iconSize: L.point(40, 40)
            });
            return L.marker(latlng, {
                icon: icon
            });
        },
        function1: function(feature, latlng) {
            // fallback defaults (in case properties are missing)
            var kiffen = feature && feature.properties && feature.properties.kiffen_erlaubt;
            var selected = feature && feature.properties && feature.properties.selected;

            var iconUrl = "assets/bench.png"; // default
            if (selected) {
                iconUrl = kiffen ? "assets/bench_kiffen_selected.png" : "assets/bench_selected.png";
            } else {
                iconUrl = kiffen ? "assets/bench_kiffen.png" : "assets/bench.png";
            }

            var flag = L.icon({
                iconUrl: iconUrl,
                iconSize: [48, 48],
                iconAnchor: [24, 48],
                popupAnchor: [0, -16]
            });
            return L.marker(latlng, {
                icon: flag
            });
        }
    }
});