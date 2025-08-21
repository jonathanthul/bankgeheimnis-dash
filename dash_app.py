import dash#type: ignore
from dash import html, dcc, no_update#type: ignore
from dash import callback_context as ctx #type:ignore
import dash_leaflet as dl#type:ignore
import json
import math
from dash_extensions.javascript import assign #type:ignore

from dash.dependencies import Input, Output, State#type: ignore
#from dash.exceptions import PreventUpdate

PLACE_NAME = "rhein-ruhr"

# Load your GeoJSON data
with open(f"geojson/{PLACE_NAME}_benches.geojson", "r") as f:
    benches_geojson = json.load(f)

benches: list = benches_geojson["features"]
def round_up(x):
    return math.ceil(x / 10) * 10    
def round_down(x):
    return math.floor(x / 10) * 10
slider_bounds = {
    "toilet_max": round_up(max([bench["properties"]["toilet_dist"] for bench in benches])),
    #"toilet_min": round_down(min([bench["properties"]["toilet_dist"] for bench in benches])),
    "shop_max": round_up(max([bench["properties"]["shop_dist"] for bench in benches])),
    #"shop_min": round_down(min([bench["properties"]["shop_dist"] for bench in benches])),
    "street_max": round_up(max([bench["properties"]["street_dist"] for bench in benches])),
    #"street_min": round_down(max([bench["properties"]["street_dist"] for bench in benches]))
}

with open(f"geojson/{PLACE_NAME}_mask.geojson", "r") as f:
    mask_geojson = json.load(f)

with open(f"geojson/{PLACE_NAME}_nichtkiffen.geojson", "r") as f:
    nichtkiffen_geojson = json.load(f)

toilet_icon = dict(
    iconUrl="assets/toilet.png",
    #shadowUrl="https://leafletjs.com/examples/custom-icons/leaf-shadow.png",
    iconSize=[48, 48],
    #shadowSize=[50, 64],
    iconAnchor=[24, 48],
    #shadowAnchor=[16, 32],
    popupAnchor=[24, 48],
)

shop_icon = dict(
    iconUrl="assets/shop.png",
    #shadowUrl="https://leafletjs.com/examples/custom-icons/leaf-shadow.png",
    iconSize=[48, 48],
    #shadowSize=[50, 64],
    iconAnchor=[24, 48],
    #shadowAnchor=[16, 32],
    popupAnchor=[24, 48],
)

#Determines cluster color and relegates cluster text style to css class marker-cluster
cluster_to_layer = assign("""function(feature, latlng, index, context){
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

# pointToLayer picks icon based on feature.properties.kiffen_erlaubt and feature.properties.selected
draw_bench = assign("""function(feature, latlng){
    // fallback defaults (in case properties are missing)
    var kiffen = feature && feature.properties && feature.properties.kiffen_erlaubt;
    var selected = feature && feature.properties && feature.properties.selected;

    var iconUrl = "assets/bench.png";  // default
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
    return L.marker(latlng, {icon: flag});
}""")

# Initialize Dash app
app = dash.Dash(__name__, title="bankgeheimnis")
server = app.server

# Layout with map and GeoJSON overlay
app.layout = html.Div([
    dcc.Store(id="panel-state", data="visible"),
    html.Button("☰", id="toggle-button", n_clicks=0, className="toggle-btn"),
    html.Div(id="control-panel", children=[
        html.Label("Entfernung zur nächsten öff. Toilette", htmlFor="toilet_slider"),
        dcc.RangeSlider(
            min=0, max=slider_bounds["toilet_max"], step=10, value=[0,200], marks=None, tooltip={"placement": "bottom", "always_visible": True, "style": {"color": "White", "fontSize": "14px"}, "template": "{value} m"},
            id="toilet-slider",
            updatemode='mouseup' #only updates when the user stops clicking, avoiding redrawing constantly
            #marks=None,
            #tooltip={"placement": "bottom", "always_visible": True}
        ),
        html.Label("Entfernung zum nächsten Laden", htmlFor="shop_slider"),
        dcc.RangeSlider(
            min=0, max=slider_bounds["shop_max"], step=10, value=[0,300], marks=None, tooltip={"placement": "bottom", "always_visible": True, "style": {"color": "White", "fontSize": "14px"}, "template": "{value} m"},
            id="shop-slider",
            updatemode='mouseup'
        ),
        html.Label("Entfernung zur nächsten großen Straße", htmlFor="street_slider"),
        dcc.RangeSlider(
            min=0, max=slider_bounds["street_max"], step=10, value=[0,1000], marks=None, tooltip={"placement": "bottom", "always_visible": True, "style": {"color": "White", "fontSize": "14px"}, "template": "{value} m"},
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
    html.Div(id="bench-info-box"),

    # Store selected bench
    dcc.Store(id="selected-bench", data=None),
    # Store filtered benches
    dcc.Store(id="filtered-benches-store"),

    dl.Map(id="map", center=[51.2277, 6.7735], zoom=13, preferCanvas=True, children=[
        dl.TileLayer(
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attribution='&copy; <a href="https://carto.com/">CARTO</a>' #adds a little link text in the bottom right
        ),
        dl.GeoJSON(  # static city boundary layer
            data=mask_geojson,
            options=dict(style=dict(color="black", weight=0, fillOpacity=0.5))
        ),
        dl.GeoJSON(
            id="bench-layer",
            interactive=True,
            zoomToBoundsOnClick=True,
            pointToLayer=draw_bench,
            cluster=True,
            superClusterOptions={"radius": 50, "maxZoom": 15},
            clusterToLayer=cluster_to_layer,
            #cluster=True, superClusterOptions={"maxZoom": 14, "maxClusterRadius": 500},
            ),
            #{"radius": 30, "maxZoom": 16},
        dl.LayerGroup(id="nichtkiffen-layer", interactive=False),
        dl.LayerGroup(id="nearby-layer"), 
    ], style={'width': '100%', 'height': '100vh'}),
])

@app.callback(
    Output("filtered-benches-store", "data"),
    Output("bench-count", "children"),

    Input("toilet-slider", "value"),
    Input("shop-slider", "value"),
    Input("street-slider", "value"),
    Input("kiffen-checkbox", "value")
)

def filter_benches2(toilet_range, shop_range, street_range, kiffen):

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
    
    print(f"filter_benches2: {len(filtered_benches)} filtered benches.")

    return filtered_benches, f'{len(filtered_benches)} Bänke gefunden.'

@app.callback(
    Output("bench-layer", "data"), #Outputs the geojson that actually gets displayed

    Input("filtered-benches-store", "data"), #Takes the list of filtered benches
    Input("selected-bench", "data"), #And info on the selected bench
)

def update_bench_layer(filtered_benches, selected_bench):
    if not filtered_benches: return {"type": "FeatureCollection", "features": []} #Safety thing?

    for bench in filtered_benches:
        bench["properties"]["selected"] = (bench["properties"]["id"] == selected_bench) #Set the property as the appropriate truth value

    #Turn the list of benches into the correct format for dl.GeoJSON
    filtered_geojson = {
    "type": "FeatureCollection",
    "features": filtered_benches
    }    
    
    return filtered_geojson

@app.callback(
    Output("nichtkiffen-layer", "children"),
    Input("kiffen-checkbox", "value"),
)

def update_nichtkiffen_layer(checkbox_value):
    nichtkiffen_layer = dl.GeoJSON(data=nichtkiffen_geojson, options=dict(style=dict(color="red", weight=1, fillOpacity=0.05))) if checkbox_value else None
    return nichtkiffen_layer

@app.callback(
    Output("selected-bench", "data"),
    Input("bench-layer", "clickData"),
    State("selected-bench", "data"),
    prevent_initial_call=True,
)

def update_selected(clicked_bench, selected_id):
    if clicked_bench:
        #fetch id of clicked bench
        clicked_id = clicked_bench["properties"]["id"] 
        #compare it to id of currently selected bench. Unselected the bench if its the same, otherwise update currently selected bench
        return None if clicked_id == selected_id else clicked_id
    #don't do anything if no bench was clicked
    return dash.no_update

@app.callback(
        Output("nearby-layer", "children"), #updates the nearby markers

        Input("selected-bench", "data"), #gets selected bench id
        Input("bench-layer", "data"), #and geojson with filtered benches from other callback
)

def render_nearby(selected_bench, filtered_geojson):
    if not selected_bench: #if nothing is selected, return nothing
        return []
    
    #This block checks if the selected_bench is contained in the list of filtered benches. If not, it returns an empty list of nearby features []
    features = (filtered_geojson or {}).get("features", []) #Safe way to get the list of features (benches), even if there is no filtered_geojson you get an empty list
    bench = next((f for f in features if f["properties"].get("id") == selected_bench), None) #Find the feature in the current filtered features with the id of selected_bench; if none exists, give me None
    if bench is None:
        # bench got filtered out -> nothing to show
        return []
    
    #bench is either None or the selected bench.
    # Use bench properties to construct nearby children (same logic as you had)
    props = bench["properties"]
    bench_geom = bench["geometry"]
    bench_pos = [bench_geom["coordinates"][1], bench_geom["coordinates"][0]]

    children = []
    # toilet
    toilet_lon, toilet_lat = props.get("toilet_lon"), props.get("toilet_lat")
    toilet_dist = props.get("toilet_dist")
    if toilet_lat and toilet_lon:
        toilet_pos = [toilet_lat, toilet_lon]
        children.append(dl.Marker(position=toilet_pos, icon=toilet_icon))
        children.append(dl.Polyline(positions=[toilet_pos, bench_pos], color="black", weight=1))
        mid = [(bench_pos[0] + toilet_pos[0]) / 2, (bench_pos[1] + toilet_pos[1]) / 2]
        children.append(dl.CircleMarker(center=mid, radius=0.1, opacity=0, fillOpacity=0,
                                       children=[dl.Tooltip(f"{toilet_dist:.0f} m", permanent=True,
                                                            direction="center", className="distance-label")]))

    # shop
    shop_lon, shop_lat = props.get("shop_lon"), props.get("shop_lat")
    shop_dist = props.get("shop_dist")
    shop_name = props.get("shop_name")
    shop_hours = props.get("shop_opening_hours")
    if shop_lat and shop_lon:
        shop_pos = [shop_lat, shop_lon]
        def construct_shop_hours_html(hours):
            # Split hours by "; " and interleave with <br> tags
            hours_lines = [line for line in hours.split("; ") if line]
            html_lines = []
            for i, line in enumerate(hours_lines):
                html_lines.append(line)
                if i < len(hours_lines) - 1:  # don't add <br> after the last line
                    html_lines.append(html.Br())
            return html_lines

        shop_tooltip_text = []
        if shop_name:
            shop_tooltip_text.append(shop_name)
        if shop_name and shop_hours:
            shop_tooltip_text.append(html.Br())
        if shop_hours:
            shop_tooltip_text.extend(construct_shop_hours_html(shop_hours))
        
        if shop_tooltip_text:  # if there’s something to show in tooltip
            print(f"tooltip text: {shop_tooltip_text}")
            shop_marker = dl.Marker(
                position=shop_pos,
                icon=shop_icon,
                children=[dl.Tooltip(
                    shop_tooltip_text,
                    direction="bottom",
                    permanent=True,
                    className="shop-label",
                    offset={"x": 0, "y": 16}
                )]
            )
        else:  # no tooltip
            shop_marker = dl.Marker(position=shop_pos, icon=shop_icon)        

        # build tooltip children
        children.append(shop_marker)
        children.append(dl.Polyline(positions=[shop_pos, bench_pos], color="black", weight=1))
        mid = [(bench_pos[0] + shop_pos[0]) / 2, (bench_pos[1] + shop_pos[1]) / 2]
        children.append(dl.CircleMarker(center=mid, radius=0.1, opacity=0, fillOpacity=0,
                                       children=[dl.Tooltip(f"{shop_dist:.0f} m", permanent=True,
                                                            direction="center", className="distance-label")]))

    return children

@app.callback(
    Output("bench-info-box", "children"),
    Input("selected-bench", "data"),
    State("bench-layer", "data"),
)
def show_bench_link(selected_bench, bench_layer_data):
    # bench_layer_data is the currently visible FeatureCollection from filter_benches
    if not selected_bench or not bench_layer_data:
        return ""  # nothing to show

    features = (bench_layer_data or {}).get("features", [])
    bench = next((f for f in features if f.get("properties", {}).get("id") == selected_bench), None)
    if bench is None:
        # selected bench is not visible under current filters -> hide link
        return ""

    coords = bench.get("geometry", {}).get("coordinates", [])
    if not coords or len(coords) < 2:
        return ""

    lon, lat = coords[0], coords[1]
    nav_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    return html.Div(
            html.A("Bank in Google Maps öffnen", href=nav_url, target="_blank", id="bench-link-inner"),
            id="bench-link-box",
        )

@app.callback(
    Output("panel-state", "data"),
    Input("toggle-button", "n_clicks"),
    State("panel-state", "data"),
    prevent_initial_call=True
)
def toggle_state(n, current):
    return "visible" if current == "hidden" else "hidden"

@app.callback(
    Output("control-panel", "className"),
    Input("panel-state", "data")
)
def update_class(state):
    return f"panel {state}"

if __name__ == "__main__":
    #Timer(1, open_browser).start()
    #app.run()
    app.run(host="0.0.0.0", port=8050, debug=True)