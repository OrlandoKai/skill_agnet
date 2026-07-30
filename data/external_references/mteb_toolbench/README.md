---
annotations_creators:
- derived
language:
- eng
license: apache-2.0
multilinguality: monolingual
source_datasets:
- KaLM-Embedding/LMEB
task_categories:
- text-retrieval
task_ids: []
dataset_info:
- config_name: ToolBench-corpus
  features:
  - name: id
    dtype: string
  - name: text
    dtype: string
  - name: title
    dtype: string
  splits:
  - name: test
    num_bytes: 10750156
    num_examples: 13862
  download_size: 2967792
  dataset_size: 10750156
- config_name: ToolBench-qrels
  features:
  - name: query-id
    dtype: string
  - name: corpus-id
    dtype: string
  - name: score
    dtype: int64
  splits:
  - name: test
    num_bytes: 141750
    num_examples: 2629
  download_size: 23298
  dataset_size: 141750
- config_name: ToolBench-queries
  features:
  - name: id
    dtype: string
  - name: text
    dtype: string
  splits:
  - name: test
    num_bytes: 318366
    num_examples: 1100
  download_size: 151254
  dataset_size: 318366
configs:
- config_name: ToolBench-corpus
  data_files:
  - split: test
    path: ToolBench-corpus/test-*
- config_name: ToolBench-qrels
  data_files:
  - split: test
    path: ToolBench-qrels/test-*
- config_name: ToolBench-queries
  data_files:
  - split: test
    path: ToolBench-queries/test-*
tags:
- mteb
- text
---
<!-- adapted from https://github.com/huggingface/huggingface_hub/blob/v0.30.2/src/huggingface_hub/templates/datasetcard_template.md -->

<div align="center" style="padding: 40px 20px; background-color: white; border-radius: 12px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05); max-width: 600px; margin: 0 auto;">
  <h1 style="font-size: 3.5rem; color: #1a1a1a; margin: 0 0 20px 0; letter-spacing: 2px; font-weight: 700;">ToolBench</h1>
  <div style="font-size: 1.5rem; color: #4a4a4a; margin-bottom: 5px; font-weight: 300;">An <a href="https://github.com/embeddings-benchmark/mteb" style="color: #2c5282; font-weight: 600; text-decoration: none;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">MTEB</a> dataset</div>
  <div style="font-size: 0.9rem; color: #2c5282; margin-top: 10px;">Massive Text Embedding Benchmark</div>
</div>

LMEB procedural retrieval task based on ToolBench, retrieving API documentation relevant to a tool-use query.

|               |                                             |
|---------------|---------------------------------------------|
| Task category | Retrieval (text-to-text)                              |
| Domains       | Programming, Web                               |
| Reference     | [LMEB: Long-horizon Memory Embedding Benchmark](https://huggingface.co/datasets/mangopy/ToolRet-Queries) |

Source datasets:
- [KaLM-Embedding/LMEB](https://huggingface.co/datasets/KaLM-Embedding/LMEB)


## How to evaluate on this task

You can evaluate an embedding model on this dataset using the following code:

```python
import mteb

task = mteb.get_task("ToolBench")
model = mteb.get_model(YOUR_MODEL)
mteb.evaluate(model, task)
```

<!-- Datasets want link to arxiv in readme to autolink dataset with paper -->
To learn more about how to run models on `mteb` task check out the [GitHub repository](https://github.com/embeddings-benchmark/mteb).

## Citation

If you use this dataset, please cite the dataset as well as [mteb](https://github.com/embeddings-benchmark/mteb), as this dataset likely includes additional processing as a part of the [MMTEB Contribution](https://github.com/embeddings-benchmark/mteb/tree/main/docs/mmteb).

```bibtex

@misc{zhao2026lmeb,
  archiveprefix = {arXiv},
  author = {Zhao, Xinping and Hu, Xinshuo and Xu, Jiaxin and Tang, Danyu and Zhang, Xin and Zhou, Mengjia and Zhong, Yan and Zhou, Yao and Shan, Zifei and Zhang, Meishan and Hu, Baotian and Zhang, Min},
  eprint = {2603.12572},
  primaryclass = {cs.CL},
  title = {LMEB: Long-horizon Memory Embedding Benchmark},
  url = {https://arxiv.org/abs/2603.12572},
  year = {2026},
}


@article{enevoldsen2025mmtebmassivemultilingualtext,
  title={MMTEB: Massive Multilingual Text Embedding Benchmark},
  author={Kenneth Enevoldsen and Isaac Chung and Imene Kerboua and Márton Kardos and Ashwin Mathur and David Stap and Jay Gala and Wissam Siblini and Dominik Krzemiński and Genta Indra Winata and Saba Sturua and Saiteja Utpala and Mathieu Ciancone and Marion Schaeffer and Gabriel Sequeira and Diganta Misra and Shreeya Dhakal and Jonathan Rystrøm and Roman Solomatin and Ömer Çağatan and Akash Kundu and Martin Bernstorff and Shitao Xiao and Akshita Sukhlecha and Bhavish Pahwa and Rafał Poświata and Kranthi Kiran GV and Shawon Ashraf and Daniel Auras and Björn Plüster and Jan Philipp Harries and Loïc Magne and Isabelle Mohr and Mariya Hendriksen and Dawei Zhu and Hippolyte Gisserot-Boukhlef and Tom Aarsen and Jan Kostkan and Konrad Wojtasik and Taemin Lee and Marek Šuppa and Crystina Zhang and Roberta Rocca and Mohammed Hamdy and Andrianos Michail and John Yang and Manuel Faysse and Aleksei Vatolin and Nandan Thakur and Manan Dey and Dipam Vasani and Pranjal Chitale and Simone Tedeschi and Nguyen Tai and Artem Snegirev and Michael Günther and Mengzhou Xia and Weijia Shi and Xing Han Lù and Jordan Clive and Gayatri Krishnakumar and Anna Maksimova and Silvan Wehrli and Maria Tikhonova and Henil Panchal and Aleksandr Abramov and Malte Ostendorff and Zheng Liu and Simon Clematide and Lester James Miranda and Alena Fenogenova and Guangyu Song and Ruqiya Bin Safi and Wen-Ding Li and Alessia Borghini and Federico Cassano and Hongjin Su and Jimmy Lin and Howard Yen and Lasse Hansen and Sara Hooker and Chenghao Xiao and Vaibhav Adlakha and Orion Weller and Siva Reddy and Niklas Muennighoff},
  publisher = {arXiv},
  journal={arXiv preprint arXiv:2502.13595},
  year={2025},
  url={https://arxiv.org/abs/2502.13595},
  doi = {10.48550/arXiv.2502.13595},
}

@article{muennighoff2022mteb,
  author = {Muennighoff, Niklas and Tazi, Nouamane and Magne, Loïc and Reimers, Nils},
  title = {MTEB: Massive Text Embedding Benchmark},
  publisher = {arXiv},
  journal={arXiv preprint arXiv:2210.07316},
  year = {2022}
  url = {https://arxiv.org/abs/2210.07316},
  doi = {10.48550/ARXIV.2210.07316},
}
```

# Dataset Statistics
<details>
  <summary> Dataset Statistics</summary>

The following code contains the descriptive statistics from the task. These can also be obtained using:

```python
import mteb

task = mteb.get_task("ToolBench")

desc_stats = task.metadata.descriptive_stats
```

```json
{
    "test": {
        "num_samples": 14962,
        "number_of_characters": 10606353,
        "documents_text_statistics": {
            "total_text_length": 10317682,
            "min_text_length": 138,
            "average_text_length": 744.3140960900303,
            "max_text_length": 17762,
            "unique_texts": 13862
        },
        "documents_image_statistics": null,
        "documents_audio_statistics": null,
        "queries_text_statistics": {
            "total_text_length": 288671,
            "min_text_length": 70,
            "average_text_length": 262.4281818181818,
            "max_text_length": 1016,
            "unique_texts": 1099
        },
        "queries_image_statistics": null,
        "queries_audio_statistics": null,
        "relevant_docs_statistics": {
            "num_relevant_docs": 2629,
            "min_relevant_docs_per_query": 1,
            "average_relevant_docs_per_query": 2.39,
            "max_relevant_docs_per_query": 6,
            "unique_relevant_docs": 1632
        },
        "top_ranked_statistics": null,
        "hf_subset_descriptive_stats": {
            "ToolBench": {
                "num_samples": 14962,
                "number_of_characters": 10606353,
                "documents_text_statistics": {
                    "total_text_length": 10317682,
                    "min_text_length": 138,
                    "average_text_length": 744.3140960900303,
                    "max_text_length": 17762,
                    "unique_texts": 13862
                },
                "documents_image_statistics": null,
                "documents_audio_statistics": null,
                "queries_text_statistics": {
                    "total_text_length": 288671,
                    "min_text_length": 70,
                    "average_text_length": 262.4281818181818,
                    "max_text_length": 1016,
                    "unique_texts": 1099
                },
                "queries_image_statistics": null,
                "queries_audio_statistics": null,
                "relevant_docs_statistics": {
                    "num_relevant_docs": 2629,
                    "min_relevant_docs_per_query": 1,
                    "average_relevant_docs_per_query": 2.39,
                    "max_relevant_docs_per_query": 6,
                    "unique_relevant_docs": 1632
                },
                "top_ranked_statistics": null
            }
        }
    }
}
```

</details>

---
*This dataset card was automatically generated using [MTEB](https://github.com/embeddings-benchmark/mteb)*