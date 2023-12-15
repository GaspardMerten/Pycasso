import itertools
import os
from math import log

import pandas as pd
from matplotlib import pyplot as plt
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from components.source import SOURCE_DATA_COLS
from src.framework.component import Component


class KMeansOutliers(Component):
    def run(self, source: pd.DataFrame) -> pd.DataFrame:
        os.environ["LOKY_MAX_CPU_COUNT"] = "4"
        # Initialize KMeans
        kmeans = KMeans(n_clusters=10, n_init='auto')

        outliers = pd.DataFrame()

        # Run KMeans for each permutation of 3 columns
        permutations = itertools.permutations(SOURCE_DATA_COLS, 2)

        for perm in list(permutations):
            source_features = source[list(perm)].values

            # Normalize the data
            source_features = StandardScaler().fit_transform(source_features)

            # Fit the model
            kmeans.fit(source_features)

            # Calculate distances to cluster centers
            distances = cdist(source_features, kmeans.cluster_centers_, "euclidean")
            min_distances = distances.min(axis=1)

            # Determine a threshold for outliers
            threshold = min_distances.mean() + 2 * min_distances.std()

            # Identify outliers
            outlier_indices = min_distances > threshold
            outliers_df = source.iloc[outlier_indices]

            # Merge with outliers
            outliers = pd.concat([outliers, outliers_df])

        outliers.sort_index(inplace=True)

        # Compute the number of outliers per train (output as a dataframe (train_id, outliers_count))
        outliers_per_train = (
            outliers.groupby("train_id").size().reset_index(name="outliers_count")
        )
        # Compute the number of rows in source per train (output as a dataframe (train_id, rows_count))
        rows_per_train = (
            source.groupby("train_id").size().reset_index(name="rows_count")
        )

        # Merge the two dataframes
        outliers_per_train = pd.merge(outliers_per_train, rows_per_train, on="train_id")
        # Compute the ratio of outliers per train (output as a dataframe (train_id, ratio))
        outliers_per_train["ratio"] = (
            outliers_per_train["outliers_count"] / outliers_per_train["rows_count"]
        )

        def normalize_with_rows_count(x):
            return min(log(x, 2), 3)

        # Multiply ratio by log of rows_count (to give more weight to trains with more rows,
        # and less weight to trains with less rows)
        outliers_per_train["ratio"] = outliers_per_train["ratio"] * outliers_per_train[
            "rows_count"
        ].apply(normalize_with_rows_count)

        mean_ratio = outliers_per_train["ratio"].mean()

        # Sort by ratio
        outliers_per_train.sort_values(by=["ratio"], inplace=True)

        # Remove trains with ratio < mean_ratio
        outliers_per_train = outliers_per_train[
            outliers_per_train["ratio"] > mean_ratio
        ]

        outliers_per_train = outliers_per_train.copy()

        # Compute intensity (rounded ratio / mean_ratio)
        outliers_per_train["intensity"] = outliers_per_train["ratio"].apply(
            lambda x: round(x / mean_ratio)
        )

        # Remove ratio column
        outliers_per_train = outliers_per_train.drop(
            columns=["ratio", "rows_count", "outliers_count"]
        )

        # Use max timestamp from source as timestamp for outliers
        outliers_per_train["timestamp"] = source.index.max()

        # Set timestamp as index
        outliers_per_train.set_index("timestamp", inplace=True)

        return outliers_per_train