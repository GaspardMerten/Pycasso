import pandas as pd

from src.framework.component import Component
from src.mining.random_forest import train_random_forest_regressor
from src.mining.residuals_to_outliers import identify_residual_outliers


class RandomForestOutliers(Component):
    def run(
        self,
        source: pd.DataFrame,
    ):
        if source.empty:
            return pd.DataFrame()

        X_columns = self.config.get("X")
        y_column = self.config.get("y")

        assert X_columns is not None, "X columns not specified"
        assert y_column is not None, "y column not specified"

        model = train_random_forest_regressor(source[X_columns], source[y_column])
        # Predict
        y_pred = model.predict(source[X_columns])

        outliers = identify_residual_outliers(
            source[y_column], y_pred, self.config.get("std_multiplier", 3)
        )

        # Inner join with source to get the train_id
        outliers = outliers.merge(source, left_index=True, right_index=True)

        return outliers
