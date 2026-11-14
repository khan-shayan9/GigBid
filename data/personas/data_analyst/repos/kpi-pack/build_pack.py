# source: synthetic · persona: data_analyst · repo: kpi-pack
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages


def on_time_rate(deliveries: pd.DataFrame) -> pd.Series:
    deliveries["on_time"] = deliveries["delivered_at"] <= deliveries["promised_by"]
    return deliveries.groupby(deliveries["delivered_at"].dt.to_period("W"))["on_time"].mean()


def build_pack(deliveries: pd.DataFrame, path: str) -> None:
    with PdfPages(path) as pdf:
        fig, ax = plt.subplots(figsize=(8, 4))
        on_time_rate(deliveries).plot(ax=ax, title="On-time delivery by week")
        ax.set_ylim(0, 1)
        pdf.savefig(fig)
        plt.close(fig)
