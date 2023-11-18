import argparse
import sys
from collections import namedtuple
from typing import *

import joblib
import mimic_pipeline.utils as utils
import numpy as np
import pandas as pd
from mimic_pipeline.feature import BinBinarizer
from mimic_pipeline.metric import get_calibration_curve, get_model_size
from mimic_pipeline.model import (AdaBoostClassifier,
                                  ExplainableBoostingClassifier, FasterRisk,
                                  LogisticRegression, RandomForestClassifier,
                                  XGBClassifier)
from sklearn.metrics import (auc, brier_score_loss, precision_recall_curve,
                             roc_curve)
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from tqdm import tqdm

import wandb

fasterrisk_ops = {"onehot": BinBinarizer(interval_width=1, whether_interval=False, group_sparsity=True)}

OPS = {
    "fasterrisk": fasterrisk_ops,
}

MODELS = {
    "fasterrisk": FasterRisk,
}

PARAMS_FR = {
    "fasterrisk-10": {
        "fold1": dict(gap_tolerance=0.3, group_sparsity=10, k=40, lb=-50, select_top_m=1, ub=120),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=10, k=40, lb=-90, select_top_m=1, ub=70),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=10, k=40, lb=-90, select_top_m=1, ub=70),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=10, k=40, lb=-120, select_top_m=1, ub=90),
        "fold5": dict(gap_tolerance=0.3, group_sparsity=10, k=40, lb=-120, select_top_m=1, ub=90),
    },
    "fasterrisk-14": {
        "fold1": dict(gap_tolerance=0.3, group_sparsity=14, k=50, lb=-70, select_top_m=1, ub=120),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=14, k=40, lb=-30, select_top_m=1, ub=30),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=14, k=30, lb=-50, select_top_m=1, ub=120),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=14, k=50, lb=-90, select_top_m=1, ub=50),
        "fold5": dict(gap_tolerance=0.3, group_sparsity=14, k=40, lb=-50, select_top_m=1, ub=70),
    },
    "fasterrisk-15": {
        "fold1": dict(gap_tolerance=0.3, group_sparsity=15, k=50, lb=-120, select_top_m=1, ub=120),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=15, k=40, lb=-90, select_top_m=1, ub=50),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=15, k=50, lb=-50, select_top_m=1, ub=120),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=15, k=50, lb=-70, select_top_m=1, ub=120),
        "fold5": dict(gap_tolerance=0.3, group_sparsity=15, k=40, lb=-70, select_top_m=1, ub=120),
    },
    "fasterrisk-16": {
        "fold5": dict(gap_tolerance=0.3, group_sparsity=16, k=40, lb=-50, select_top_m=1, ub=90),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=16, k=50, lb=-70, select_top_m=1, ub=70),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=16, k=50, lb=-70, select_top_m=1, ub=50),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=16, k=50, lb=-90, select_top_m=1, ub=120),
        "fold1": dict(gap_tolerance=0.3, group_sparsity=16, k=70, lb=-90, select_top_m=1, ub=90),
    },
    "fasterrisk-17": {
        "fold5": dict(gap_tolerance=0.3, group_sparsity=17, k=40, lb=-70, select_top_m=1, ub=70),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=17, k=60, lb=-70, select_top_m=1, ub=70),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=17, k=40, lb=-70, select_top_m=1, ub=30),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=17, k=60, lb=-50, select_top_m=1, ub=90),
        "fold1": dict(gap_tolerance=0.3, group_sparsity=17, k=40, lb=-30, select_top_m=1, ub=50),
    },
    "fasterrisk-18": {
        "fold5": dict(gap_tolerance=0.3, group_sparsity=18, k=50, lb=-50, select_top_m=1, ub=50),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=18, k=70, lb=-50, select_top_m=1, ub=50),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=18, k=50, lb=-30, select_top_m=1, ub=30),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=18, k=50, lb=-50, select_top_m=1, ub=30),
        "fold1": dict(gap_tolerance=0.3, group_sparsity=18, k=80, lb=-70, select_top_m=1, ub=70),
    },
    "fasterrisk-19": {
        "fold5": dict(gap_tolerance=0.3, group_sparsity=19, k=60, lb=-90, select_top_m=1, ub=70),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=19, k=60, lb=-90, select_top_m=1, ub=90),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=19, k=80, lb=-70, select_top_m=1, ub=50),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=19, k=50, lb=-30, select_top_m=1, ub=50),
        "fold1": dict(gap_tolerance=0.3, group_sparsity=19, k=50, lb=-30, select_top_m=1, ub=90),
    },
    "fasterrisk-20":{
        "fold1": dict(gap_tolerance=0.3, group_sparsity=20, k=50, lb=-50, select_top_m=1,ub=90),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=20, k=60, lb=-70, select_top_m=1, ub=70),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=20, k=50, lb=-30, select_top_m=1, ub=70),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=20, k=60, lb=-90, select_top_m=1, ub=30),
        "fold5": dict(gap_tolerance=0.3, group_sparsity=20, k=60, lb=-70, select_top_m=1, ub=30),
    },
    "fasterrisk-25":{
        "fold1": dict(gap_tolerance=0.3, group_sparsity=25, k=50, lb=-50, select_top_m=1, ub=50),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=25, k=70, lb=-90, select_top_m=1, ub=50),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=25, k=60, lb=-30, select_top_m=1, ub=90),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=25, k=70, lb=-90, select_top_m=1, ub=30),
        "fold5": dict(gap_tolerance=0.3, group_sparsity=25, k=60, lb=-90, select_top_m=1, ub=30),
    },
    "fasterrisk-30":{
        "fold1": dict(gap_tolerance=0.3, group_sparsity=30, k=50, lb=-30, select_top_m=1, ub=90),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=30, k=70, lb=-70, select_top_m=1, ub=70),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=30, k=50, lb=-70, select_top_m=1, ub=30),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=30, k=40, lb=-90, select_top_m=1, ub=30),
        "fold5": dict(gap_tolerance=0.3, group_sparsity=30, k=40, lb=-50, select_top_m=1, ub=30),
    },
    "fasterrisk-35":{
        "fold1": dict(gap_tolerance=0.3, group_sparsity=35, k=60, lb=-70, select_top_m=1, ub=70),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=35, k=70, lb=-90, select_top_m=1, ub=70),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=35, k=70, lb=-50, select_top_m=1, ub=50),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=35, k=50, lb=-70, select_top_m=1, ub=70),
        "fold5": dict(gap_tolerance=0.3, group_sparsity=35, k=70, lb=-70, select_top_m=1, ub=50),
    },
    "fasterrisk-40": {
        "fold1": dict(gap_tolerance=0.3, group_sparsity=40, k=60, lb=-90, select_top_m=1, ub=70),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=40, k=70, lb=-90, select_top_m=1, ub=90),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=40, k=70, lb=-70, select_top_m=1, ub=90),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=40, k=50, lb=-30, select_top_m=1, ub=50),
        "fold5": dict(gap_tolerance=0.3, group_sparsity=40, k=70, lb=-50, select_top_m=1, ub=90),
    },
    "fasterrisk-45":{
        "fold1": dict(gap_tolerance=0.3, group_sparsity=45, k=60, lb=-90, select_top_m=1, ub=90),
        "fold2": dict(gap_tolerance=0.3, group_sparsity=45, k=70, lb=-90, select_top_m=1, ub=70),
        "fold3": dict(gap_tolerance=0.3, group_sparsity=45, k=70, lb=-70, select_top_m=1, ub=30),
        "fold4": dict(gap_tolerance=0.3, group_sparsity=45, k=50, lb=-30, select_top_m=1, ub=90),
        "fold5": dict(gap_tolerance=0.3, group_sparsity=45, k=50, lb=-70, select_top_m=1, ub=90),
    },
}

def cross_validation(model, param_dict: dict, disease: str, operations: dict, save_path: str=None, verbose: bool=False) -> Optional[dict]:
    stats = {'auroc': [], 'auprc': [], 'precision': [], 'recall': [], 'h-stat': [], 'fpr': [], 'tpr': [], 'true_prob': [], 'pred_prob': [], 'h-p-value': [], 'c-stat': [], 'c-p-value': [], 'brier': [], "smr": [], 'complexity': []}
    model_name = model().__class__.__name__
    pbar = tqdm(range(1, 6), desc=f"Fold 1 for {model_name}...")
    for i in pbar:
        train = pd.read_csv(f"src/exp_6.6_to_6.27/data/mimic-disease/k-fold-id/TRAIN-{disease}-fold{i}.csv")
        test = pd.read_csv(f"src/exp_6.6_to_6.27/data/mimic-disease/k-fold-id/TEST-{disease}-fold{i}.csv")
        param = param_dict[f'fold{i}']
        
        X_train, y_train = train.drop('hospital_expire_flag', axis=1), train['hospital_expire_flag']
        X_test, y_test = test.drop('hospital_expire_flag', axis=1), test['hospital_expire_flag']
        pbar.set_description(desc=f"Fold {i} for {model_name} | apply operations...")
        X_train, y_train, X_test, GroupIdx = utils.apply_ops(X_train, y_train, X_test, operations, verbose=verbose)      # NOTE: no need to store fitted transforms for MIMIC cross validation
        
        if isinstance(model(), FasterRisk):
            param['featureIndex_to_groupIndex'] = GroupIdx
        elif isinstance(model(), XGBClassifier):
            y_train = y_train.replace({-1: 0})
            y_test = y_test.replace({-1: 0})
            
        init_model = model(**param)
        pbar.set_description(f"Fold {i} for {model_name} | training model...")
        init_model.fit(X_train, y_train)
        y_prob = init_model.predict_proba(X_test)
        
        if len(y_prob.shape) == 2:        # for some scikit-learn models where probas is 2D
            y_prob = y_prob[:, 1]
        
        pbar.set_description(desc=f"Fold {i} for {model_name} | calculating metrics...")
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        auroc = auc(fpr, tpr)
        precision, recall, _ = precision_recall_curve(y_test, y_prob)
        auprc = auc(recall, precision)
        prob_true, prob_pred, h_stat, p_h = get_calibration_curve(y_test, y_prob)
        _, _, c_stat, p_c = get_calibration_curve(y_test, y_prob, strategy='quantile')
        brier = brier_score_loss(y_test, y_prob)
        smr = np.sum(y_test.replace({-1: 0})) / np.sum(y_prob)
        complexity = get_model_size(init_model)
        
        stats['auroc'].append(auroc)
        stats['auprc'].append(auprc)
        stats['precision'].append(precision)
        stats['recall'].append(recall)
        stats['fpr'].append(fpr)
        stats['tpr'].append(tpr)
        stats['true_prob'].append(prob_true)
        stats['pred_prob'].append(prob_pred)
        stats['h-stat'].append(h_stat)
        stats['h-p-value'].append(p_h)
        stats['c-stat'].append(c_stat)
        stats['c-p-value'].append(p_c)
        stats['brier'].append(brier)
        stats['smr'].append(smr)
        stats['complexity'].append(complexity)

    if save_path is not None:
        terminal = sys.stdout
        sys.stdout = open(f"{save_path}.txt", "wt")
    print(f"Model: {model_name}")
    print(f"AUROC: {np.asarray(stats['auroc']).mean():.3f} $\pm$ {np.asarray(stats['auroc']).std():.3f}")
    print(f"AUPRC: {np.asarray(stats['auprc']).mean():.3f} $\pm$ {np.asarray(stats['auprc']).std():.3f}")
    print(f"Hosmer Lemeshow H stat: {np.asarray(stats['h-stat']).mean():.3f} $\pm$ {np.asarray(stats['h-stat']).std():.3f}")
    print(f"Hosmer Lemeshow C stat: {np.asarray(stats['c-stat']).mean():.3f} $\pm$ {np.asarray(stats['c-stat']).std():.3f}")
    print(f"Brier Score: {np.asarray(stats['brier']).mean():.3f} $\pm$ {np.asarray(stats['brier']).std():.3f}")
    print(f"SMR: {np.asarray(stats['smr']).mean():.3f} $\pm$ {np.asarray(stats['smr']).std():.3f}")
    if save_path is not None:
        sys.stdout = terminal
    
    if save_path is not None:
        joblib.dump(stats, save_path)
        print(f"Results saved as \"{save_path}\" and \"{save_path}.txt\"")
    else:
        return stats

if __name__ == "__main__":
    prs = argparse.ArgumentParser()
    prs.add_argument("--algo", dest="algo", type=str, default='fasterrisk-10')
    prs.add_argument("--save_path", dest="save_path", type=str, default='auto')
    prs.add_argument("--disease", dest="disease", type=str, default='akf')
    args = prs.parse_args()
    
    # wandb.init(
    #     entity='dukeds-mimic2023',
    #     project='MIMIC (6.15)',
    #     name=f'FasterRisk-CV-Disease_{args.disease}_{args.algo}',
    #     group='FasterRisk MIMIC',
    #     save_code=True,
    # )
    
    if args.save_path == 'auto':
        args.save_path = f"src/exp_6.6_to_6.27/results/disease/{args.disease}/{args.algo}"
    
    print(args)
    model = MODELS['fasterrisk'] if 'fasterrisk' in args.algo else MODELS[args.algo]
    operations = OPS['fasterrisk'] if 'fasterrisk' in args.algo else OPS[args.algo]
    cross_validation(model=model, param_dict=PARAMS_FR[args.algo], disease=args.disease, operations=operations, save_path=args.save_path)