import dash#type: ignore
from dash import html, dcc, no_update#type: ignore
import dash_leaflet as dl#type:ignore
import json
import geopandas as gpd#type:ignore
from threading import Timer
import webbrowser
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
    "toilet_min": round_down(min([bench["properties"]["toilet_dist"] for bench in benches])),
    "shop_max": round_up(max([bench["properties"]["shop_dist"] for bench in benches])),
    "shop_min": round_down(min([bench["properties"]["shop_dist"] for bench in benches])),
    "street_max": round_up(max([bench["properties"]["street_dist"] for bench in benches])),
    "street_min": round_down(max([bench["properties"]["street_dist"] for bench in benches]))
}

#According to ChatGPT, each bench needs an id that is not nested in properties for clickData to detect clicks on bench markers. I have not found that to be true, so I commented it out for now.
#for i, feat in enumerate(benches_geojson["features"]):
#    feat.setdefault("id", i)

with open(f"geojson/{PLACE_NAME}_mask.geojson", "r") as f:
    mask_geojson = json.load(f)

with open(f"geojson/{PLACE_NAME}_nichtkiffen.geojson", "r") as f:
    nichtkiffen_geojson = json.load(f)

toilet_icon = dict(
    iconUrl="assets/toilet.png",
    #shadowUrl="https://leafletjs.com/examples/custom-icons/leaf-shadow.png",
    iconSize=[48, 48],
    #shadowSize=[50, 64],
    iconAnchor=[16, 48],
    #shadowAnchor=[16, 32],
    popupAnchor=[16, 32],
)

shop_icon = dict(
    iconUrl="assets/shop.png",
    #shadowUrl="https://leafletjs.com/examples/custom-icons/leaf-shadow.png",
    iconSize=[48, 48],
    #shadowSize=[50, 64],
    iconAnchor=[16, 48],
    #shadowAnchor=[16, 32],
    popupAnchor=[16, 32],
)

#followed these instructions to make it work: https://www.dash-leaflet.com/docs/geojson_tutorial#a-custom-icons
draw_bench = assign("""function(feature, latlng){
const flag = L.icon({iconUrl: `assets/bench4.png`, iconSize: [32, 32]});
return L.marker(latlng, {icon: flag});
}""")

draw_bench = assign("""function(feature, latlng){
    let iconUrl;
    if (feature.properties.kiffen_erlaubt) {
        iconUrl = "assets/bench_kiffen.png";   // or whatever image you want
    } else {
        iconUrl = "assets/bench4.png";
    }
    const flag = L.icon({
        iconUrl: iconUrl,
        iconSize: [48, 48],
        iconAnchor: [16, 48],
        popupAnchor: [0, -16]
    });
    return L.marker(latlng, {icon: flag});
}""")

# Initialize Dash app
app = dash.Dash(__name__)

# Layout with map and GeoJSON overlay
app.layout = html.Div([
    
    html.Div(id="control-panel", children=[
        html.Label("Distance to Toilet (m)", htmlFor="toilet_slider"),
        dcc.RangeSlider(
            min=0, max=slider_bounds["toilet_max"], step=10, value=[0,200], marks=None, tooltip={"placement": "bottom", "always_visible": True},
            id="toilet_slider",
            updatemode='mouseup' #only updates when the user stops clicking, avoiding redrawing constantly
            #marks=None,
            #tooltip={"placement": "bottom", "always_visible": True}
        ),
        html.Label("Distance to shop (m)", htmlFor="shop_slider"),
        dcc.RangeSlider(
            min=0, max=slider_bounds["shop_max"], step=10, value=[0,300], marks=None, tooltip={"placement": "bottom", "always_visible": True},
            id="shop_slider",
            updatemode='mouseup'
        ),
        html.Label("Distance to big streets (m)", htmlFor="street_slider"),
        dcc.RangeSlider(
            min=0, max=slider_bounds["street_max"], step=10, value=[0,1000], marks=None, tooltip={"placement": "bottom", "always_visible": True},
            id="street_slider",
            updatemode='mouseup'
        ),
        dcc.Checklist(
            options=[{"label": "Kiffen erlaubt", "value": "kiffen"}],
            value=[],
            id="kiffen_checkbox"
        ),
        ]),
        html.Div(id="bench-counter", children=[
            html.Label(id="bench-count"),
        ]),

    dcc.Store(id="selected-bench", data=None),

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
            superClusterOptions={"radius": 30, "maxZoom": 16},
            #cluster=True, superClusterOptions={"maxZoom": 14, "maxClusterRadius": 500},
            ),
        dl.LayerGroup(id="nichtkiffen-layer", interactive=False),
        dl.LayerGroup(id="nearby-layer"), 
    ], style={'width': '100%', 'height': '100vh'}),
])

@app.callback(
    Output("bench-layer", "data"),
    Output("bench-count", "children"),
    Output("nichtkiffen-layer", "children"),

    Input("toilet_slider", "value"),
    Input("shop_slider", "value"),
    Input("street_slider", "value"),
    Input("kiffen_checkbox", "value"),
)

def filter_benches(toilet_range: list, shop_range: list, street_range: list, kiffen: list):
    features = benches_geojson["features"] #grab the list of benches from the GeoJSON file

    #print statements for debug purposes
    print("toilet_range:", toilet_range)
    print("shop_range:", shop_range)
    print("street_range:", street_range)
    print("kiffen_checkbox:", kiffen)

    filtered_benches = [f for f in features 
                if f["properties"].get("toilet_dist") is not None and
                    toilet_range[0] <= f["properties"]["toilet_dist"] <= toilet_range[1]
                and f["properties"].get("shop_dist") is not None and
                    shop_range[0] <= f["properties"]["shop_dist"] <= shop_range[1]
                and f["properties"].get("street_dist") is not None and
                    street_range[0] <= f["properties"]["street_dist"] <= street_range[1]  
                and (f["properties"]["kiffen_erlaubt"] or ("kiffen" not in kiffen))
                ]
    
    #print statement for debug
    print(f"Number of filtered benches: {len(filtered_benches)}")

    # Add popup HTML string to each feature
    # this is essentially what you did in the create_bench_marker function, except you pass it to a built-in dl.GeoJSON thing in the end
    for f in filtered_benches:
        #fetch the relevant numbers to make the subsequent code easier to read
        street_dist = f["properties"]["street_dist"]
        nichtkiffen_text = "Kiffen nicht erlaubt"
        if f["properties"]["kiffen_erlaubt"]:
            nichtkiffen_text = "Kiffen erlaubt"

        lat, lon = f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]
        nav_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

        #build a big string containing html code that shoud be shown when clicking on a bench marker
        popup_html = (
            f'<a href="{nav_url}" target="_blank">In Google Maps öffnen.</a>'
        )

        tooltip_text = f"{nichtkiffen_text}. {street_dist:.0f} m zur nächsten großen Straße"
        tooltip_html = f'<a href="{nav_url}" target="_blank">In Google Maps öffnen.</a>'

        f["properties"]["popup"] = popup_html #dl.GeoJSON recognized a "popup" property. You add the info compiled above to such a property in the in-memory data structure that python works with
        f["properties"]["tooltip"] = tooltip_text

    filtered_geojson = {
    "type": "FeatureCollection",
    "features": filtered_benches
    }

    nichtkiffen_layer = dl.GeoJSON(
        data=nichtkiffen_geojson,
        options=dict(style=dict(color="red", weight=1, fillOpacity=0.05))
    ) if kiffen else None

    return (
        filtered_geojson, #this list might contain the children for the output?
        f"{len(filtered_benches)} Bänke gefunden.",
        nichtkiffen_layer,
        )
# this stacks because, if you had already checked the toilet filter, that filtered list is being filtered again after checking another box!

@app.callback(
    Output("selected-bench", "data"),
    Input("bench-layer", "click_feature"),
    prevent_initial_call=True
)
def store_selected_bench(feature):
    print(f"store_selected feature: {feature}")
    if feature is None:
        return None
    return feature["properties"]["id"]   # your bench id

@app.callback(
    Output("nearby-layer", "children"),

    #Input("bench-layer", "n_clicks"), #this just counts the total number of clicks by the user on the bench layer afaict
    Input("bench-layer", "clickData"), #this records the properties of the clicked object/marker. Doesn't trigger a callback when it changes though
    prevent_initial_call=True
)
def on_bench_click(clickData):
    bench_props = clickData.get("properties")
    bench_id = bench_props.get("id")
    bench_geom = clickData.get("geometry")
    bench_pos = [bench_geom.get("coordinates")[1], bench_geom.get("coordinates")[0]]

    props = clickData.get("properties") if isinstance(clickData, dict) else {} #check if clickData is a dict as expected and grab the contained properties dict. Otherwise return empty dict. This will break if your GeoJSON has an unexpected structure
    toilet_distance = props.get("toilet_dist") #type: ignore
    shop_distance = props.get("shop_dist")#type: ignore
    shop_name = props.get("shop_name")#type: ignore
    shop_hours = props.get("shop_opening_hours")#type: ignore

    toilet_lon, toilet_lat = props.get("toilet_lon"), props.get("toilet_lat")
    toilet_pos = [toilet_lat, toilet_lon]
    shop_lon, shop_lat = props.get("shop_lon"), props.get("shop_lat")
    shop_pos = [shop_lat, shop_lon]

    print(f"Last clicked bench: {bench_id} | {bench_pos}")
    print(f"Closest toilet: https://www.google.com/maps/search/?api=1&query={toilet_lat},{toilet_lon}")
    print(f"Closest shop: {shop_name}, https://www.google.com/maps/search/?api=1&query={shop_lat},{shop_lon}")

    toilet_children = []
    shop_children = []

    if toilet_lat and toilet_lon:
        toilet_marker = dl.Marker(position=toilet_pos, icon=toilet_icon,)

        toilet_children.append(toilet_marker) #toilet marker
        toilet_children.append(dl.Polyline(positions=[toilet_pos, bench_pos], color="black", weight=1)) #toilet line

        mid_pos = [(bench_pos[0] + toilet_pos[0]) / 2, (bench_pos[1] + toilet_pos[1]) / 2]
        toilet_children.append(
            dl.CircleMarker(
                center=mid_pos, radius=0.1, opacity=0, fillOpacity=0,
                children=[dl.Tooltip(f"{toilet_distance:.0f} m", permanent=True, direction="center",className="distance-label")]
            )
        )

    if shop_lat and shop_lon: #if there is a shop position
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

            #tooltips display weird when there's not info on them
            #could try truncating hours by ";" and putting each part in a new line
            #need to figure out the offset option for tooltips

        shop_children.append(shop_marker)
        shop_children.append(dl.Polyline(positions=[shop_pos, bench_pos], color="black", weight=1))

        mid_pos = [(bench_pos[0] + shop_pos[0])/2, (bench_pos[1] + shop_pos[1])/2]
        shop_children.append(
            dl.CircleMarker(
                center=mid_pos, radius=0.1, opacity=0, fillOpacity=0,
                children=[dl.Tooltip(f"{shop_distance:.0f} m", permanent=True, direction="center", className="distance-label")]
            )
        )

    #what you want to return is a list of toilet children, each of which is a dl.Marker
    return toilet_children + shop_children

def open_browser():
    webbrowser.open("http://127.0.0.1:8050/")

if __name__ == "__main__":
    #Timer(1, open_browser).start()
    app.run()