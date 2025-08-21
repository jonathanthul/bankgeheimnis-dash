import dash
from dash import html
from dash.dependencies import Input, Output
import dash_leaflet as dl

app = dash.Dash(__name__)

# Example data
benches = [
    {"id": 0, "coords": (51.2277, 6.7735)},
    {"id": 1, "coords": (51.2300, 6.7800)},
]
shops = [(51.2285, 6.7740), (51.2310, 6.7790)]
toilets = [(51.2270, 6.7720), (51.2320, 6.7810)]

# Use dictionary for icon options
bench_icon = {"iconUrl": "/assets/bench.png", "iconSize": [25, 25]}
shop_icon = {"iconUrl": "/assets/shop.png", "iconSize": [25, 25]}
toilet_icon = {"iconUrl": "/assets/toilet.png", "iconSize": [25, 25]}

def compute_closest(point, options):
    return min(options, key=lambda o: (point[0]-o[0])**2 + (point[1]-o[1])**2)

app.layout = html.Div([
    dl.Map(
        center=(51.228, 6.774),
        zoom=15,
        style={'width': '100%', 'height': '500px'},
        children=[
            dl.TileLayer(),
            dl.LayerGroup(id="bench-layer", children=[
                dl.Marker(
                    id=f"bench-{b['id']}",
                    position=b["coords"],
                    icon=bench_icon,
                    children=dl.Tooltip(f"Bench {b['id']}")
                ) for b in benches
            ]),
            dl.LayerGroup(id="highlight-layer")
        ]
    )
])

@app.callback(
    Output("highlight-layer", "children"),
    [Input(f"bench-{b['id']}", "n_clicks") for b in benches]
)
def show_closest(*n_clicks_list):
    for i, clicks in enumerate(n_clicks_list):
        if clicks:
            bench_coords = benches[i]["coords"]
            closest_shop = compute_closest(bench_coords, shops)
            closest_toilet = compute_closest(bench_coords, toilets)
            return [
                dl.Marker(position=closest_shop, icon=shop_icon, children=dl.Tooltip("Closest Shop")),
                dl.Marker(position=closest_toilet, icon=toilet_icon, children=dl.Tooltip("Closest Toilet")),
                dl.Polyline(positions=[bench_coords, closest_shop], color="blue"),
                dl.Polyline(positions=[bench_coords, closest_toilet], color="green")
            ]
    return []

if __name__ == "__main__":
    app.run(debug=True)
