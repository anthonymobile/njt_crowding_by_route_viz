import pandas as pd
from pandas.api.types import CategoricalDtype
from NJTransitAPI import *


class Bundle():
    def __init__(self, stoplist, dataframe):
        self.stoplist = stoplist
        self.dataframe = dataframe

# get route geometry and pack into a flat list (e.g. 2 services in 2 directions = 4 list items)
def get_paths(route):
    data, fetch_timestamp = get_xml_data('nj', 'route_points', route=route)
    geometry = parse_xml_getRoutePoints(data)
    # unpack the first list of Routes
    route = geometry[0]
    return route.paths

def load_data(route):
    
    data = pd.read_parquet(
        f"https://njtransit-crowding-data.s3.amazonaws.com/njt-crowding-route-{route}.parquet"
    )
    
    # drop those without ETA_min
    data.dropna(subset=['eta_min'])
    
    # drop no crowding data; encode crowding
    data.drop(data.loc[data['crowding']=='NO DATA'].index,inplace=True)
    
    # drop non-nyc destinations (119 only)
    data.drop(data.loc[data['destination']=='BAYONNE'].index,inplace=True)
    
    #drop duplicate rows
    data.drop_duplicates(
        subset=['bus_id','eta_time'], 
        keep=False
        )
    
    # recode as ordered categorical type
    # https://towardsdatascience.com/how-to-do-a-custom-sort-on-pandas-dataframe-ac18e7ea5320
    cat_crowding = CategoricalDtype(
        ['LIGHT', 'MEDIUM', 'HEAVY'],
        ordered=True
        )
    data['crowding'] = data['crowding'].astype(cat_crowding)

    # create path, data bundles for chart making
    
    # get geometry
    paths = get_paths(route)
    
    bundles = []
    
    for path in paths:

        # FIRST get_stoplist_df
        stoplist = path.get_stoplist_df()
        
        # second filter fetched data based on direction from Route.Path
        df = data[data['destination'] == path.d]
    
        # THIRD join them so the df has stop info in it
        df = pd.merge(
            df,
            stoplist,
            on='stop_id',
            how='left'
            )
        
        # FOURTH pack them into a Bundle
        bundle = Bundle(stoplist, df)
        
        # FIFTH path that Bundle into a list
        bundles.append(bundle)
    
    return bundles