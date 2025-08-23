import dash #type:ignore
from dash import html, dcc#type:ignore
import dash_leaflet as dl #type:ignore
from dash_extensions.javascript import assign #type:ignore
from dash.dependencies import Input, Output, State #type:ignore
from shapely.geometry import Polygon, mapping, shape #type:ignore
import json

PLACE_NAME = "rhein-ruhr"

app = dash.Dash(__name__, title="bankgeheimnis")

# tell python to use the drawBench function declared in the javascript file. This is a weird workaround where you tell it call an arrow function that calls your original function, but it's the only way to make it work without having dash-extensions look for a nonexistent function0
draw_bench = assign('(feature, latlng, context) => window.drawBench(feature, latlng, context)') 

draw_cluster = assign("""function(feature, latlng, index, context){
    const scatterIcon = L.DivIcon.extend({
        createIcon: function(oldIcon) {
            let icon = L.DivIcon.prototype.createIcon.call(this, oldIcon);
            icon.style.backgroundColor = 'rgba(255,255,255,0.7)';  // fixed color
            return icon;
        }
    });
    const icon = new scatterIcon({
        html: '<div><span>' + feature.properties.point_count_abbreviated + '</span></div>',
        className: "marker-cluster",
        iconSize: L.point(40, 40)
    });
    return L.marker(latlng, {icon: icon});
}""")

# Helper functions for clipping away stuff out of viewport
def bounds_to_polygon(map_bounds):
    sw = map_bounds["_southWest"]
    ne = map_bounds["_northEast"]
    nw = {"lat": ne["lat"], "lng": sw["lng"]}
    se = {"lat": sw["lat"], "lng": ne["lng"]}
    coords = [
        (sw["lng"], sw["lat"]),
        (nw["lng"], nw["lat"]),
        (ne["lng"], ne["lat"]),
        (se["lng"], se["lat"]),
        (sw["lng"], sw["lat"])  # close ring
    ]
    return Polygon(coords)
    
def clip_FeatureCollection(bounds, full_geojson):
    viewport_poly = bounds_to_polygon(bounds)
    clipped_features = []

    for feature in full_geojson.get("features", []):
        geom = shape(feature["geometry"])
        clipped = geom.intersection(viewport_poly)
        if not clipped.is_empty:
            clipped_features.append({
                "type": "Feature",
                "properties": feature.get("properties", {}),
                "geometry": mapping(clipped)
            })

    return {"type": "FeatureCollection", "features": clipped_features}

# Load your GeoJSON data
with open(f"geojson/{PLACE_NAME}_benches.geojson", "r") as f:
    benches_geojson = json.load(f)
with open(f"geojson/{PLACE_NAME}_mask.geojson", "r") as f:
    mask_geojson = json.load(f)
with open(f"geojson/{PLACE_NAME}_nichtkiffen.geojson", "r") as f:
    nichtkiffen_geojson = json.load(f)

app.layout = html.Div([
    dcc.Store(id="panel-state", data="visible"),
    dcc.Store(id="filtered-benches-store"),
    html.Button("☰", id="toggle-button", n_clicks=0, className="toggle-btn"),
    html.Div(id="control-panel", children=[
        html.Label("Entfernung zur nächsten öff. Toilette", htmlFor="toilet_slider"),
        dcc.RangeSlider(
            min=0, max=5000, step=10, value=[0,200], marks=None, tooltip={"placement": "bottom", "always_visible": True, "style": {"color": "White", "fontSize": "14px"}, "template": "{value} m"},
            id="toilet-slider",
            updatemode='mouseup' #only updates when the user stops clicking, avoiding redrawing constantly
            #marks=None,
            #tooltip={"placement": "bottom", "always_visible": True}
        ),
        html.Label("Entfernung zum nächsten Laden", htmlFor="shop_slider"),
        dcc.RangeSlider(
            min=0, max=5000, step=10, value=[0,300], marks=None, tooltip={"placement": "bottom", "always_visible": True, "style": {"color": "White", "fontSize": "14px"}, "template": "{value} m"},
            id="shop-slider",
            updatemode='mouseup'
        ),
        html.Label("Entfernung zur nächsten großen Straße", htmlFor="street_slider"),
        dcc.RangeSlider(
            min=0, max=5000, step=10, value=[0,1000], marks=None, tooltip={"placement": "bottom", "always_visible": True, "style": {"color": "White", "fontSize": "14px"}, "template": "{value} m"},
            id="street-slider",
            updatemode='mouseup',
        ),
        dcc.Checklist(
            options=[{"label": "Kiffen erlaubt", "value": "kiffen"}],
            value=[],
            id="kiffen-checkbox"
        ),
        html.Label("Zähle Bänke", id="bench-count"),
        ]),
    dl.Map(center=[51.2277, 6.7735], zoom=13, style={'height': '100vh'},
           children=[
                dl.TileLayer(
                    url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                    attribution='&copy; <a href="https://carto.com/">CARTO</a>', #adds a little link text in the bottom right   +
                    id="map",
               ),
               dl.GeoJSON(
                    data=mask_geojson,
                    options=dict(style=dict(color="black", weight=0, fillOpacity=0.5))
               ),
                dl.GeoJSON(
                    data=benches_geojson,
                    options=dict(pointToLayer=draw_bench),
                    id="bench-layer",
                    cluster=True,
                    clusterToLayer=draw_cluster,
                    zoomToBoundsOnClick=True,
                    hideout=dict(),
                ),
                dl.LayerGroup(id="nichtkiffen-layer", interactive=False),
           ])
])

# Take filter input, return appropriate benches wrappen in GeoJSON strcture to bench-layer
@app.callback(
    Output("bench-layer", "data"),
    Output("bench-count", "children"),

    Input("toilet-slider", "value"),
    Input("shop-slider", "value"),
    Input("street-slider", "value"),
    Input("kiffen-checkbox", "value")
)
def filter_benches(toilet_range, shop_range, street_range, kiffen):

    benches = benches_geojson["features"]
    
    filtered_benches = [bench for bench in benches
                if bench["properties"].get("toilet_dist") is not None and
                    toilet_range[0] <= bench["properties"]["toilet_dist"] <= toilet_range[1]
                and bench["properties"].get("shop_dist") is not None and
                    shop_range[0] <= bench["properties"]["shop_dist"] <= shop_range[1]
                and bench["properties"].get("street_dist") is not None and
                    street_range[0] <= bench["properties"]["street_dist"] <= street_range[1]  
                and (bench["properties"]["kiffen_erlaubt"] or ("kiffen" not in kiffen))
                ]
    
    print(f"filter_benches: {len(filtered_benches)} filtered benches.")

    #wrap it as geojson so you can directly hand it to dl.GeoJSON
    filtered_geojson = {"type": "FeatureCollection", "features": filtered_benches}

    return filtered_geojson, f'{len(filtered_benches)} Bänke gefunden.'

# Listen to clicks on toggle-button. Switch current status and return ot to panel-state
@app.callback(
    Output("panel-state", "data"),
    Input("toggle-button", "n_clicks"),
    State("panel-state", "data"),
    prevent_initial_call=True
)
def toggle_state(n, current):
    return "visible" if current == "hidden" else "hidden"

# Listen to changes in panel-state, change div class of control-panel accordingly. style.css then somehow runs the little hiding
@app.callback(
    Output("control-panel", "className"),
    Input("panel-state", "data")
)
def update_class(state):
    return f"panel {state}"

# Listen to nichtkiffen_checkbox, if checked, return GeoJSON layer to nichtkiffen-layer dl.LayerGroup
@app.callback(
    Output("nichtkiffen-layer", "children"),
    Input("kiffen-checkbox", "value"),
    Input("map", "bounds"),
)
def update_nichtkiffen_layer(checkbox_value, map_bounds):
    nichtkiffen_layer = dl.GeoJSON(data=nichtkiffen_geojson, options=dict(style=dict(color="red", weight=1, fillOpacity=0.05))) if checkbox_value else None
    return nichtkiffen_layer

if __name__ == "__main__":
    app.run(debug=True)
