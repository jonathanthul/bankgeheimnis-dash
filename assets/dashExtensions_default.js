window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: (feature, latlng, context) => window.drawBench(feature, latlng, context),
        function1: function(feature, latlng, index, context) {
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
        }
    }
});