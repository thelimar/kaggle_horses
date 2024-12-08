# -*- coding: utf-8 -*-
"""Horses_Konoplia_Gorbulya.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1XNxX0S9f7EMneuj7_xixaT-sY8eqTZYN
"""

# This Python 3 environment comes with many helpful analytics libraries installed
# It is defined by the kaggle/python Docker image: https://github.com/kaggle/docker-python
# For example, here's several helpful packages to load

import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)

# Input data files are available in the read-only "../input/" directory
# For example, running this (by clicking run or pressing Shift+Enter) will list all files under the input directory

import os
for dirname, _, filenames in os.walk('/kaggle/input'):
    for filename in filenames:
        print(os.path.join(dirname, filename))

# You can write up to 20GB to the current directory (/kaggle/working/) that gets preserved as output when you create a version using "Save & Run All"
# You can also write temporary files to /kaggle/temp/, but they won't be saved outside of the current session

import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.impute import KNNImputer, SimpleImputer
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import KFold
from sklearn.metrics import f1_score
from sklearn.preprocessing import PowerTransformer

from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier
from xgboost import XGBClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, VotingClassifier

"""# Loading data"""

train = pd.read_csv('/kaggle/input/playground-series-s3e22/train.csv')
test = pd.read_csv('/kaggle/input/playground-series-s3e22/test.csv')
origin = pd.read_csv('/kaggle/input/horse-survival-dataset/horse.csv')

# id does not seem to represent anything in this synthetic dataset, so lets drop it
train.drop('id',axis=1,inplace=True)
test.drop('id',axis=1,inplace=True)

train = pd.concat([train, origin], ignore_index=True)
train.drop_duplicates(inplace=True)

print('Train size:', train.shape)
print('Test size', test.shape)

"""# EDA"""

train.describe()

summary = pd.DataFrame(train.dtypes, columns=['dtypes'])
summary['missing_values'] = train.isna().sum()
summary['unique_values'] = train.nunique().values
summary['all_values'] = train.count().values

summary.style.background_gradient()

"""As we can see object type indicates that the feature is categorical, and the rest are numerical. The exception is hospital_number, because its number is basically a name, not the numerical value that represent something."""

numerical = []
categorial = []

for col in train.columns:
    if train[col].dtype == "object":
        categorial.append(col)
    else:
        numerical.append(col)

print(f"Numerical: {numerical}")
print(f"Categorial: {categorial}")

plt.figure(figsize=(12, 12))
corr_matrix = train[numerical].corr()
sns.heatmap(corr_matrix, cmap="coolwarm")
plt.title('Correlation Matrix')
plt.show()

"""Lesion 2 and Lesion 3 (what is lesion...) seem correlated, so it might be benefitial to drop one.

We will count feature importance after preprocessing, but that's all for now.

# Preprocessing

For ordinal categorial we will manually asign labels, for not ordinal we will use one hot, and if feature has a lot of unique values and we do not care about the order or it is binary, we will use label encoding. We will not change numerical features (apart from hospital number), as decision trees are not sensible to scaling. We will impute the values with KNN imputer for numerical features, and simple imputer for categorial features with most common values. Also, some values are named differently in train and test, for example 'slight' appeared in train instead of 'moderate' in test for the 'pain' column.
"""

traintest = pd.concat([train, test], ignore_index=True)

if 'hospital_number' in numerical:
    numerical.remove('hospital_number')
    categorial.append('hospital_number')

categorial.remove('mucous_membrane')
categorial.remove('outcome')

traintest['hospital_number'] = traintest['hospital_number'].astype('string')

traintest['outcome'] = traintest['outcome'].map({'died':0,'euthanized':1,'lived':2})

traintest

one_hot = ['mucous_membrane']
label = ["hospital_number", "age", "surgical_lesion", "surgery", "cp_data"]

traintest["pain"] = traintest["pain"].replace('slight', 'moderate')
traintest["rectal_exam_feces"] = traintest["rectal_exam_feces"].replace('serosanguious', 'absent')
traintest["nasogastric_reflux"] = traintest["nasogastric_reflux"].replace('slight', 'none')
traintest['mucous_membrane'] = traintest['mucous_membrane'].fillna('other')

traintest = pd.get_dummies(traintest, columns = one_hot)


label_encoder = LabelEncoder()
for col in label:
    traintest[col] = label_encoder.fit_transform(traintest[col])

traintest["abdomo_appearance"] = traintest["abdomo_appearance"].map({'clear': 0, 'cloudy': 1, 'serosanguious': 2})
traintest["abdomen"] = traintest["abdomen"].map({'normal': 0, 'other': 1, 'firm': 2,'distend_small': 3, 'distend_large': 4})
traintest["temp_of_extremities"] = traintest["temp_of_extremities"].map({'cold': 0, 'cool': 1, 'normal': 2, 'warm': 3})
traintest["nasogastric_reflux"] = traintest["nasogastric_reflux"].map({'less_1_liter': 0, 'none': 1, 'more_1_liter': 2})
traintest["peristalsis"] = traintest["peristalsis"].map({'hypermotile': 0, 'distend_small': 1, 'normal': 2, 'hypomotile': 3, 'absent': 4})
traintest["abdominal_distention"] = traintest["abdominal_distention"].map({'none': 0, 'slight': 1, 'moderate': 2, 'severe': 3})
traintest["nasogastric_tube"] = traintest["nasogastric_tube"].map({'none': 0, 'slight': 1, 'significant': 2})
traintest["capillary_refill_time"] = traintest["capillary_refill_time"].map({'less_3_sec': 0, '3': 1, 'more_3_sec': 2})
traintest["pain"] = traintest["pain"].map({'alert': 0, 'depressed': 1, 'moderate': 2, 'mild_pain': 3, 'severe_pain': 4, 'extreme_pain': 5})
traintest["rectal_exam_feces"] = traintest["rectal_exam_feces"].map({'absent': 0, 'decreased': 1, 'normal': 2, 'increased': 3})
traintest["peripheral_pulse"] = traintest["peripheral_pulse"].map({'absent': 0, 'reduced': 1, 'normal': 2, 'increased': 3})

num_imputer = KNNImputer(n_neighbors = 10)
cat_imputer = SimpleImputer(strategy = 'most_frequent')

traintest[categorial] = cat_imputer.fit_transform(traintest[categorial])
traintest[numerical] = num_imputer.fit_transform(traintest[numerical])

traintest[categorial] = traintest[categorial].astype("int64")
traintest[traintest.select_dtypes('bool').columns] = traintest[traintest.select_dtypes('bool').columns].astype('int64')

traintest

processed_train = traintest[traintest['outcome'].notna()]
processed_test = traintest[traintest['outcome'].isna()]
processed_test.drop('outcome', axis=1, inplace=True)

print('Train size:', processed_train.shape)
print('Test size', processed_test.shape)

processed_train['outcome'] = processed_train['outcome'].astype("int64")

"""# Baseline

For the baseline we will have lgbm classifier
"""

model = LGBMClassifier(
    max_depth= 10,
    n_estimators= 1000,
    random_state= 55,
    class_weight = 'balanced',
    verbose=-1
)

def fit_and_validate(model, processed_train, processed_test, write_submition = False):
    X = processed_train[processed_test.columns.tolist()]
    Y = processed_train['outcome']

    k_folds = KFold(n_splits=3, shuffle=True, random_state=55)
    f1_scores = []

    for train_idx, test_idx in k_folds.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = Y.iloc[train_idx], Y.iloc[test_idx]

        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        f1 = f1_score(y_test, preds, average = 'micro')
        f1_scores.append(f1)

    if write_submition:
        model.fit(X, Y)
        prediction = model.predict(processed_test)

        answer = pd.read_csv('/kaggle/input/playground-series-s3e22/sample_submission.csv')
        answer['outcome'] = prediction
        answer['outcome'] = answer['outcome'].astype('int64')
        answer['outcome'] = answer['outcome'].map({0:'died',1:'euthanized',2:'lived'})
        answer.to_csv("submission.csv", index=False)

    return np.mean(f1_scores)

final_score = fit_and_validate(model, processed_train, processed_test)

print(f"Baseline model's score is: {final_score}")

"""# Improvements

First, let's calculate feature importance
"""

feature_imps = model.feature_importances_
features = processed_test.columns.tolist()

combined = zip(feature_imps, features)
combined = sorted(combined, key = lambda x: x[0])

feature_imps = [elem[0] for elem in combined]
features = [elem[1] for elem in combined]

plt.figure(figsize=(15, 12))
plt.barh(features, feature_imps)
plt.title("Feature importance")

plt.show()

"""## Feature generation"""

processed_traintest = pd.concat([processed_train, processed_test], ignore_index=True)
processed_traintest['normal_temp_relation'] = processed_traintest['rectal_temp'] / 37.8
processed_traintest['normal_pulse_relation'] = processed_traintest['pulse'] / 36

power_transform = PowerTransformer(method='yeo-johnson')
processed_traintest['yj_lesion1'] = power_transform.fit_transform(processed_traintest['lesion_1'].to_numpy().reshape((-1, 1)))
processed_traintest['yj_packed_cell_volume'] = power_transform.fit_transform(processed_traintest['packed_cell_volume'].to_numpy().reshape((-1, 1)))

processed_train = processed_traintest[processed_traintest['outcome'].notna()]
processed_test = processed_traintest[processed_traintest['outcome'].isna()]
processed_test.drop('outcome', axis=1, inplace=True)

processed_test.shape

"""Let's check if it helped!"""

model = LGBMClassifier(
    max_depth= 10,
    n_estimators= 1000,
    random_state= 55,
    class_weight = 'balanced',
    verbose=-1
)

final_score = fit_and_validate(model, processed_train, processed_test)

print(f"Added features model's score is: {final_score}")

"""Well, it didn't help) This configuration at least does not hinder results, other generation configurations I tried waas even worse) May be things will be different after discarding some features

## Feature selection
"""

import shap

shap_test = shap.TreeExplainer(model).shap_values(processed_train[processed_test.columns.tolist()])

shap.summary_plot(shap_test, processed_train[processed_test.columns.tolist()])

shap_total = np.abs(shap_test).mean(axis=(0, 1))

shap_df = pd.DataFrame([processed_train[processed_test.columns.tolist()].columns.tolist(), shap_total.tolist()]).T
shap_df.columns = ['feature', 'shap_score']
shap_df = shap_df.sort_values('shap_score', ascending=False)
shap_df

significant_features = shap_df[shap_df['shap_score'] >= 0.01]['feature'].values.tolist()
significant_features

processed_test = processed_test[significant_features]
significant_features.append('outcome')
processed_train = processed_train[significant_features]

print('Train size:', processed_train.shape)
print('Test size', processed_test.shape)

model = LGBMClassifier(
    max_depth= 10,
    n_estimators= 1000,
    random_state= 55,
    class_weight = 'balanced',
    verbose=-1
)

X = processed_train[processed_test.columns.tolist()]
Y = processed_train['outcome']

k_folds = KFold(n_splits=3, shuffle=True, random_state=55)
f1_scores = []

for train_idx, test_idx in k_folds.split(X):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = Y.iloc[train_idx], Y.iloc[test_idx]

    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    f1 = f1_score(y_test, preds, average = 'micro')
    f1_scores.append(f1)

final_score = np.mean(f1_scores)

print(f"Excluded features model's score is: {final_score}")

"""Well we have some boost! But very very veryyy insignificant :(
Now it's time for real improvement, let's change the model to ensemble.

## Ensemble modeling
"""

lgbm_cls = LGBMClassifier(
    max_depth= 10,
    n_estimators= 1000,
    random_state= 55,
    class_weight = 'balanced',
    verbose=-1

)

xgb_cls = XGBClassifier(
    n_estimators= 500,
    objective= 'multi:softmax',
    class_weight= 'balanced',
    random_state= 55,
    max_depth= 1
)

cat_cls = CatBoostClassifier(
    iterations = 600,
    depth = 3,
    random_state= 55
)

hist_cls = HistGradientBoostingClassifier(
    l2_regularization= 0.01,
    early_stopping= True,
    max_depth= 4,
    min_samples_leaf= 10,
    max_leaf_nodes=10,
    class_weight='balanced',
    max_iter=1000,
    random_state= 55
)

models = [
    ("lgbm", lgbm_cls),
    ("xgb", xgb_cls),
    ("cat", cat_cls),
    ("hist", hist_cls)
]

voting_ensemble = VotingClassifier(estimators=models, voting='soft')

final_score = fit_and_validate(voting_ensemble, processed_train, processed_test)

print(f"Ensemble model's score is: {final_score}")

"""YAY! Finally, some significant boost! What is left is basically to tune hyperparameters, ideally we want to use something like optune, but there is no time..."""

lgbm_cls = LGBMClassifier(
    max_depth= 10,
    n_estimators= 1000,
    random_state= 55,
    class_weight = 'balanced',
    verbose=-1

)

xgb_cls = XGBClassifier(
    n_estimators= 600,
    objective= 'multi:softmax',
    class_weight= 'balanced',
    random_state= 55,
    max_depth= 1,
    verbose=-1
)

cat_cls = CatBoostClassifier(
    iterations = 600,
    depth = 3,
    random_state= 55,
    verbose=False
)

hist_cls = HistGradientBoostingClassifier(
    l2_regularization= 0.01,
    early_stopping= True,
    max_depth= 4,
    min_samples_leaf= 10,
    max_leaf_nodes=10,
    class_weight='balanced',
    max_iter=1000,
    random_state= 55,
    verbose=False
)

models = [
    ("lgbm", lgbm_cls),
    ("xgb", xgb_cls),
    ("cat", cat_cls),
    ("hist", hist_cls)
]
voting_ensemble = VotingClassifier(estimators=models, voting='soft',weights=[1, 3, 3, 1])

final_score = fit_and_validate(voting_ensemble, processed_train, processed_test, write_submition=True)

print(f"Optimized ensemble model's score is: {final_score}")