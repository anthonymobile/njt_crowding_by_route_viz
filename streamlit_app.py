# -*- coding: utf-8 -*-

from cProfile import label
from datetime import datetime
import altair as alt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

#TODO: pass as kwarg from outside
route = "119"

# SETTING PAGE CONFIG TO WIDE MODE AND ADDING A TITLE AND FAVICON
st.set_page_config(layout="wide", page_title="CROWDR: Visualizing Poor Service on NJTransit", page_icon=":bus:")

# LOAD DATA ONCE
# @st.experimental_singleton
def load_data():
    
    cols = [
        "timestamp",
        "route",
        "stop_id", 
        "destination",
        "headsign",
        "vehicle_id", 
        "eta_min", 
        "eta_time", 
        "crowding"]
    
    datatypes = {
                "timestamp": str,
        "route": str,
        "stop_id": str, 
        "destination": str,
        "headsign": str,
        "vehicle_id": str, 
        "eta_min": str,
        "eta_time": str,
        "crowding": str
    }
    
    data = pd.read_csv(
        f"https://njtransit-crowding-data.s3.amazonaws.com/njt-crowding-route-{route}.csv",
        names= cols,
        dtype=datatypes,
        error_bad_lines=False,
        parse_dates=["timestamp"]
    )
    
    st.dataframe(data)
    breakpoint()
    # drop no crowding data; encode crowding; change < 1 eta to 0
    data.drop(data.loc[data['crowding']=='NO DATA'].index,inplace=True)
    
    # drop non-nyc destinations (119 only)
    data.drop(data.loc[data['destination']=='NEW YORK'].index,inplace=True)
    
    # drop those without ETA_min
    data.dropna(subset=['eta_min'])
    
    # recode data    
    data['crowding_int'] = data['crowding'].replace({'LIGHT': 1, 'MEDIUM': 2, 'HEAVY': 3}).astype(int)
    data['eta_min'] = data['eta_min'].replace({'< 1': 0}).astype(int)

    return data



# FILTER DATA FOR A SPECIFIC HOUR, CACHE
@st.experimental_memo
def filterdata(df, hour_selected):
    return df[df["timestamp"].dt.hour == hour_selected]


# STREAMLIT APP LAYOUT
data = load_data()

# LAYING OUT THE TOP SECTION OF THE APP
row1_1, row1_2 = st.columns((2, 3))

# SEE IF THERE'S A QUERY PARAM IN THE URL (e.g. ?service_hour=2)
# THIS ALLOWS YOU TO PASS A STATEFUL URL TO SOMEONE WITH A SPECIFIC HOUR SELECTED,
# E.G. https://share.streamlit.io/streamlit/demo-uber-nyc-pickups/main?service_hour=2
if not st.session_state.get("url_synced", False):
    try:
        service_hour = int(st.experimental_get_query_params()["service_hour"][0])
        st.session_state["service_hour"] = service_hour
        st.session_state["url_synced"] = True
    except KeyError:
        pass

# IF THE SLIDER CHANGES, UPDATE THE QUERY PARAM
def update_query_params():
    hour_selected = st.session_state["service_hour"]
    st.experimental_set_query_params(service_hour=hour_selected)


with row1_1:
    st.title("Overcrowding on the 119")
    st.subheader("The view from Congress St and Webster Ave")
    hour_selected = st.slider(
        "Select hour of service", 0, 23, key="service_hour", on_change=update_query_params
    )


with row1_2:
    l = len(data)
    
    st.write("""
    ##
    The 119 is one of the most important bus routes in The Heights, linking Central Avenue to New York City. But during rush hour, buses are often full by the time they reach Palisade Avenue, and bypass stranded passengers.
    """)
    

    st.write(
    f"""The charts below summarize {l} observations scraped from NJTransit apps since {data['timestamp'].min().date()} to illustrate how bus overcrowding is experienced by riders at one stop where riders are often left behind. 
    """)
    st.write(
        """
         By sliding the slider on the left you can choose an hour of the day, and see how buses fill up as they approach this stop during different times of day.
        """
    )
    

#######################################################
# CROWDING BAR CHART

# FILTER DATA BY HOUR
@st.experimental_memo
def plotdata3(df, hr):
    filtered = data[
        (df["timestamp"].dt.hour >= hr) & (df["timestamp"].dt.hour < (hr + 1))
    ]

    # https://stackoverflow.com/questions/50465860/groupby-and-count-on-dataframe-having-two-categorical-variables
    array = filtered.groupby(['eta_min','crowding']).size().reset_index(name='count')
        
    return array
    # return pd.DataFrame({"eta_min": array.index, "crowding": array})

plot_data3 = plotdata3(data, hour_selected)


st.altair_chart(
    alt.Chart(plot_data3)
    .mark_bar(
        size=20,
        cornerRadiusTopLeft=3,
        cornerRadiusTopRight=3
    )
    .encode(
        x=alt.X("eta_min:Q", scale=alt.Scale(nice=False), title="Minutes away"),
        # y=alt.Y("count:Q", scale=alt.Scale(domain=[0, 3])),
        y=alt.Y("count:Q", title="Number of Buses Observed ", axis=alt.Axis(tickMinStep=1)),
        color="crowding:N"
    )
    .configure_mark(opacity=0.4, color="red"),
    use_container_width=True,
)


#######################################################
# CROWDING HISTOGRAM


# FILTER DATA BY HOUR
@st.experimental_memo
def plotdata(df, hr):
    filtered = data[
        (df["timestamp"].dt.hour >= hr) & (df["timestamp"].dt.hour < (hr + 1))
    ]
    filtered['crowding_int'] = filtered['crowding'].replace({'LIGHT': 1, 'MEDIUM': 2, 'HEAVY': 3}).astype(int)


    array = filtered.groupby('eta_min')['crowding_int'].mean()
    
    return pd.DataFrame({"eta_min": array.index, "average_crowding": array})

plot_data = plotdata(data, hour_selected)


st.write(
    f"""**Average level of crowding on approaching buses at given ETA to Congress St & Webster Ave stop, between {hour_selected}:00 and {(hour_selected + 1) % 24}:00**"""
)


st.altair_chart(
    alt.Chart(plot_data)
    .mark_area(
        interpolate="natural",
    )
    .encode(
        x=alt.X("eta_min:Q", scale=alt.Scale(nice=False)),
        y=alt.Y("average_crowding:Q", scale=alt.Scale(domain=[0, 3])),
        tooltip=["eta_min", "average_crowding"],
    )
    .configure_mark(opacity=0.2, color="red"),
    use_container_width=True,
)



#######################################################
# OBSERVATION HISTOGRAM

# FILTER DATA BY HOUR
@st.experimental_memo
def histdata(df, hr):
    filtered = data[
        (df["timestamp"].dt.hour >= hr) & (df["timestamp"].dt.hour < (hr + 1))
    ]
    hist = np.histogram(filtered["eta_min"], bins=60, range=(0, 60))[0]
    return pd.DataFrame({"eta_min": range(60), "observations": hist})


chart_data = histdata(data, hour_selected)

# LAYING OUT THE HISTOGRAM SECTION
st.write(
    f"""**Number of observed approaching buses at given ETA to Congress St & Webster Ave stop, between {hour_selected}:00 and {(hour_selected + 1) % 24}:00**"""
)
st.altair_chart(
    alt.Chart(chart_data)
    .mark_area(
        interpolate="step-after",
    )
    .encode(
        x=alt.X("eta_min:Q", scale=alt.Scale(nice=False)),
        y=alt.Y("observations:Q"),
        tooltip=["eta_min", "observations"],
    )
    .configure_mark(opacity=0.2, color="red"),
    use_container_width=True,
)

