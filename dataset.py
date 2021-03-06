from transformers import AutoTokenizer
import random
from random import randint
import torch

class PreTrainDataset(object):
    
    def __init__(self, path, train_cfg, model_cfg):

        self.tokenizer = AutoTokenizer.from_pretrained("roberta-base")
        self.data = open(path, "r", encoding="utf-8").read().split("\n\n")

        self.batch_size = train_cfg.batch_size
        self.dataset_size = len(self.data)

        self.mask_id = model_cfg.mask_id
        self.max_len = model_cfg.max_len
        self.keep_prob = train_cfg.keep_prob

        self.max_masked_words = round(train_cfg.mask_prob * model_cfg.max_len)
        self.mask_masked_tokens_in_attn = train_cfg.mask_masked_tokens_in_attn
        
        self.step = 0
        self.dataset_indexes = [i for i in range(self.dataset_size)]

    def __iter__(self):
        
        while self.step < self.dataset_size - torch.cuda.device_count():

            data = self.data[self.step: self.step + self.batch_size]
            data = [d.split("\n") for d in data]
            data = [" ".join(d[randint(0, len(d) - 1):]) for d in data]

            batch_size = len(data)
            if batch_size % torch.cuda.device_count() != 0:
                data = data[: -batch_size % torch.cuda.device_count()]

            batch_size = len(data)

            data = self.tokenizer(data, max_length=self.max_len, padding='max_length', truncation=True, return_tensors="pt")

            label_mask = torch.zeros(batch_size, self.max_len).float()
            for i in range(batch_size):
                indices = torch.randperm(self.max_len)[:self.max_masked_words]
                label_mask[i, indices] += 1.

            label_mask *= data["attention_mask"]
            keep_mask = label_mask * torch.bernoulli(torch.ones_like(label_mask) - self.keep_prob)

            input_ids = data["input_ids"] * (1 - keep_mask) + keep_mask * self.mask_id
            label = data["input_ids"] * label_mask
            attn_mask = data["attention_mask"].float()

            if self.mask_masked_tokens_in_attn:
                attn_mask *= (1. - keep_mask)

            self.step += batch_size

            yield input_ids.long(), attn_mask.float(), label.long(), label_mask

    def reset_epoch(self):

        print("Shuffling Dataset")
        self.step = 0
        random.shuffle(self.dataset_indexes)
        self.data = [self.data[i] for i in self.dataset_indexes]
        
    def get_dataset_state(self):

        return self.step, self.dataset_indexes

    def set_dataset_state(self, step, dataset_indexes):

        self.step = step
        self.dataset_indexes = dataset_indexes
        self.data = [self.data[i] for i in dataset_indexes]
    

class FineTuneDataset(object):
    
    def __init__(self, data, labels, train_cfg, model_cfg):

        assert type(data) == list, "Expect a list of sentences"
        assert type(labels) == list, "Expect a list of labels"

        self.tokenizer = AutoTokenizer.from_pretrained("roberta-base")
        self.data = data
        self.labels = labels

        self.batch_size = train_cfg.batch_size
        self.max_len = model_cfg.max_len
        self.dataset_size = len(self.data)
        
        self.step = 0
        self.dataset_indexes = [i for i in range(self.dataset_size)]

    def __iter__(self):
        
        while self.step < self.dataset_size - torch.cuda.device_count():

            data = self.data[self.step: self.step + self.batch_size]
            label = torch.tensor(self.labels[self.step: self.step + self.batch_size])

            batch_size = len(data)
            if batch_size % torch.cuda.device_count() != 0:
                data = data[: -batch_size % torch.cuda.device_count()]
                label = label[: -batch_size % torch.cuda.device_count()]

            batch_size = len(data)

            data = self.tokenizer(data, max_length=self.max_len, padding='max_length', truncation=True, return_tensors="pt")
            input_ids = data["input_ids"] 
            attn_mask = data["attention_mask"].float()

            self.step += batch_size

            yield input_ids.long(), attn_mask.float(), label.long()

    def reset_epoch(self):

        print("Shuffling Dataset")
        self.step = 0
        random.shuffle(self.dataset_indexes)
        self.data = [self.data[i] for i in self.dataset_indexes]
        
    def get_dataset_state(self):

        return self.step, self.dataset_indexes

    def set_dataset_state(self, step, dataset_indexes):

        self.step = step
        self.dataset_indexes = dataset_indexes
        self.data = [self.data[i] for i in dataset_indexes]
    