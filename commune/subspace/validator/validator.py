import commune
import streamlit as st
import torch
from typing import Dict, List, Union, Any
import random
from copy import deepcopy

class Validator(commune.Module):
    
    def __init__(self, 
                 dataset: str = 'dataset',
                 miners: List[str]= None,
                 key: Union[Dict, str] = None,
                 metric: Union[Dict, str] = None,
                 stats: Union[Dict, None] = None,
                 alpha: float = 0.5,
                 ):
        
        self.set_dataset(dataset)
        self.set_miners(miners)
        self.set_key(key)
        self.set_metric(metric)
        self.set_stats(stats)
        self.set_alpha(alpha)
        
    def set_alpha(self, alpha: float) -> None:
        # set alpha for exponential moving average
        self.alpha = alpha
        
    def verify_signature(self, signature: Dict) -> bool:
        return True
    
    def add_miner(self, miner: str, signature: Dict = None) -> None:
        if not hasattr(self, 'miners'):
            self.miners = {}
        st.write(miner.module_id)
        st.write(miner.key)
        self.miners[miner] = commune.connect(miner)

            
    def set_miners(self, miners: List[str] = None) -> None:
        if miners is None:
            miners = self.default_miners()
            
        for miner in miners:
            self.add_miner(miner)
    
    def set_dataset(self, dataset: str) -> None:
        if isinstance(dataset, str):
            dataset = commune.connect(dataset)
        else:
            raise ValueError(f'Invalid dataset type: {type(dataset)}')
        
        self.dataset = dataset
        

    def set_metric(self, metric = None) -> None:
        if metric is None:
            metric = torch.nn.CrossEntropyLoss()
        self.metric = metric
    def calculate_metric(self, x):
        
        import torch
        input_ids = x.get('input_ids', None)
        pred = x.get('logits', None)
        if input_ids != None:
            gt = input_ids[:, -(pred.shape[1]-1):].flatten()
            pred = pred[:, :-1]
            
        assert isinstance(gt, torch.Tensor), f'gt is not a torch.Tensor. gt: {gt}'
        assert isinstance(pred, torch.Tensor), f'gt is not a torch.Tensor. gt: {gt}'
            
        if len(pred.shape) == 3:
            pred = pred.reshape(-1, pred.shape[-1])
        
        assert gt.shape == pred.shape[:1], f'gt.shape: {gt.shape} pred.shape: {pred.shape}'

        metric =  self.metric(pred, gt.to(pred.device))
        
        
        return metric.item()
    
    

    def sample(self, **kwargs):
        kwargs.update(dict(
            tokenize=True, sequence_length=10, batch_size=2
        ))
        return self.dataset.sample(**kwargs)
    @property
    def miner_keys(self):
        return list(self.miners.keys())
    
    def set_stats(self, stats: Dict[str, Any]) -> None:
        if stats is None:
            stats = {}
        self.stats = stats
        

    def get_sample_metatdata(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        sample_metadata = {}
        for k, v in sample.items():
            metadata_k = {'type': type(v)}
            
            if isinstance(v, torch.Tensor):
                metadata_k.update({
                    'shape': str(v.shape),
                    'dtype': str(v.dtype),
                })
            elif type(v) in [list, set, tuple]:
                metadata_k.update({
                    'length': len(v),
                })
            elif isinstance(v, dict):
                metadata_k.update({
                    'length': len(v),
                })
            sample_metadata[k] = metadata_k

        return sample_metadata
            
                
            
    
    def validate_miner(self, miner_key: str = None, **kwargs):
        miner_key = miner_key if miner_key else self.random_miner_key()
        miner = self.miners[miner_key]
        sample = self.sample()
        
        
        t= commune.timer()
        output = miner.forward(**sample,return_keys=['topk'])
        elapsed_time =  t.seconds
        output['input_ids'] = sample['input_ids']
        
        # calculate metric
        metric = self.calculate_metric(output)
        
        

        miner_stat={ 
                        'metric': metric,
                        'timestamp': commune.time(),
                        'elapsed_time': elapsed_time,
                        'sample_metadata': self.get_sample_metatdata(sample),
                             }
        
        
        self.set_stat(key=miner_key, stat = miner_stat)
        
        
        return metric


    def set_stat(self, key: str, stat: Dict[str, Any]) -> None:
        
        prev_stat = deepcopy(self.stats.pop(key, {}))
        if 'metric' in prev_stat:
            stat['metric'] =  self.alpha*prev_stat['metric'] + (1-self.alpha)*stat['metric']
        
        self.stats[key] = stat
        
    def calculate_weights(self):
        
        
        total_weights = 0 
        weight_map = {}
        for k in self.stats.keys():
            weight_map[k] =  1 / (self.stats[k]['metric'] + 1e-8)
            total_weights = total_weights + weight_map[k]


        for k in self.stats.keys():
            weight_map[k] = weight_map[k] / total_weights
            self.stats[k]['weight'] = weight_map[k]
            
    def random_miner_key(self):
        random_miner_key = random.choice(self.miner_keys)
        return random_miner_key

    def random_miner(self):
        random_miner_key = self.random_miner_key()
        return self.miners[random_miner_key]
    
    
    @classmethod
    def test(cls):
        miners = [m for m in commune.servers() if m.startswith('miner')]
        self = Validator(miners=miners)
        for _ in range(10):
            st.write(self.validate_miner())
        self.calculate_weights()
        st.write(self.stats)
      
    @classmethod
    def test_validation_keys(cls):
        vals = [Validator() for _ in range(10)]
        st.write([v.key.address for v in vals])
        hash = vals[0].key.hash({'hey': 'whadup'})
        sig = vals[0].key.sign(hash)
        
        assert not vals[0].key.verify(hash, signature = sig, public_key = vals[1].key.public_key )
        assert vals[0].key.verify(hash, signature = sig, public_key = vals[0].key.public_key )
        
        
    @classmethod 
    def default_miners(cls):
        return [commune.connect(m) for m in commune.servers() if m.startswith('miner')]
        
if __name__ == '__main__':

    # self = Validator(
        
    validator =  Validator(miners=None, dataset='dataset.text.glue')
    
    # st.write(self.test())