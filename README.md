proGAT

proGAT 是一个 ONT 原核基因组组装教程与分析脚本，主要用于演示从 Oxford Nanopore Technologies（ONT）长读长测序数据出发，完成原核生物基因组数据质控、基因组大小预测和基因组组装的基本流程。

本教程主要使用以下软件：

SeqKit：测序数据基本统计

fastplong：ONT 长读长数据过滤与质控

LRGE：基因组大小预测

Flye：长读长基因组组装

推荐结合 Conda 与 Docker 安装和管理上述分析软件，以减少软件依赖和环境配置问题。

1. Workflow

ONT FASTQ
   |
   v
 SeqKit
   |
   v
fastplong
   |
   v
  LRGE
   |
   | estimated genome size
   v
  Flye
   |
   v
Assembly

其中，LRGE 预测得到的 genome size 会自动传递给 Flye 的：

--genome-size

参数，因此不需要手动设置预估基因组大小。

2. Demo data

本教程可使用以下 NCBI SRA 数据作为 demo：

SRR23100672
https://trace.ncbi.nlm.nih.gov/Traces/?view=run_browser&acc=SRR23100672&display=metadata

SRR23100674
https://trace.ncbi.nlm.nih.gov/Traces/?view=run_browser&acc=SRR23100674&display=metadata

下载后的 ONT FASTQ 数据可放置于同一个输入目录中，例如：

datas/
├── SRR23100672.fastq.gz
└── SRR23100674.fastq.gz

每个 FASTQ 文件会被识别为一个独立样本。

3. Software requirements

Python

推荐使用 Python 3：

python3 --version

当前 proGAT.py 主要使用 Python 标准库，不需要额外安装 Python package。

Conda

推荐使用 Conda / Miniconda 管理本地命令行软件，例如：

conda create -n proGAT python=3.11
conda activate proGAT

可以将 SeqKit、Flye、fastplong 等软件安装到独立的 proGAT 环境中。

安装完成后建议确认：

seqkit --version
flye --version
fastplong --version

Docker

推荐使用 Docker 运行部分依赖较复杂的软件。

首先确认 Docker 可以正常使用：

docker --version

使用 Docker 的优点包括：

避免复杂的软件依赖冲突

不同计算机之间更容易复现分析环境

不需要在本地安装大量依赖

方便后续扩展 QUAST、CheckM2、BUSCO 等分析

4. Input

通过：

-i / --input

指定输入数据文件夹。

支持以下 FASTQ 格式：

.fastq.gz
.fq.gz
.fastq
.fq

例如：

datas/
├── sample1.fastq.gz
├── sample2.fastq.gz
└── sample3.fastq.gz

5. Output

通过：

-o / --output

指定分析结果输出目录。

例如：

-o ./result

主要结果会保存在该目录中。

6. Usage

查看帮助：

python3 proGAT.py -h

基本运行方式：

python3 proGAT.py \
    -i /path/to/input \
    -o /path/to/output \
    -d /path/to/database \
    -t 48

例如：

python3 proGAT.py \
    -i ./datas \
    -o ./result \
    -d ./database \
    -t 48

7. Command-line arguments

参数

长参数

是否必填

默认值

说明

-i

--input

Yes

-

输入 FASTQ 文件夹

-o

--output

Yes

-

输出结果文件夹

-d

--database

No

./database

数据库根目录

-t

--threads

No

8

使用线程数

8. Step 1 — SeqKit

SeqKit 用于快速统计原始测序数据的基本信息，例如：

reads 数量

总碱基数

平均长度

N50

最短 / 最长 reads

示例：

seqkit stats sample.fastq.gz -a -T

该步骤主要用于在正式分析前了解原始 ONT 数据的基本情况。

9. Step 2 — fastplong

fastplong 用于 ONT 长读长测序数据的过滤和质量控制。

主要输出包括：

filtered.fastq.gz
HTML report
JSON report

过滤后的 FASTQ 数据会用于后续 LRGE 和 Flye 分析。

10. Step 3 — LRGE

LRGE 用于根据长读长测序数据预测 genome size。

例如 LRGE 输出：

4426642

表示预测的 genome size 为：

4,426,642 bp

proGAT 会自动读取 LRGE 的预测结果，并将其传递给 Flye。

流程为：

FASTQ
  |
  v
LRGE
  |
  v
4426642 bp
  |
  v
Flye --genome-size 4426642

因此无需手动输入 Flye 的 genome size。

11. Step 4 — Flye

Flye 是本教程的主要基因组组装软件。

对于 ONT 高质量 reads，当前脚本使用：

--nano-hq

例如：

flye \
    --nano-hq sample_filtered.fastq.gz \
    --genome-size 4426642 \
    --out-dir ./result/flye/sample \
    --threads 48

其中：

--genome-size 4426642

由 LRGE 自动预测并传入。

Flye 的主要组装结果为：

assembly.fasta

12. Extended quality assessment

在完成 Flye 组装之后，可以继续使用以下软件评估 assembly：

QUAST

CheckM2

BUSCO

这些步骤用于进一步评估：

contig 数量

genome size

N50

GC content

Completeness

Contamination

BUSCO completeness

它们属于本教程中基因组组装后的扩展质量评估部分。

13. Output structure

例如指定：

-o ./result

输出目录大致为：

result/
├── seqkit_stats/
├── fastplong_filtered/
├── lrge/
├── flye/
├── quast/
├── checkm/
└── BUSCO/

其中最主要的组装结果位于：

result/flye/<sample>/assembly.fasta

14. Recommended repository structure

推荐 GitHub 仓库结构：

proGAT/
├── proGAT.py
├── README.md
├── .gitignore
└── example/

不建议将原始测序数据、数据库或完整分析结果直接上传至 GitHub。

建议在 .gitignore 中加入：

*.fastq
*.fastq.gz
*.fq
*.fq.gz

database/
result/

.DS_Store
__pycache__/

15. Notes

当前教程主要面向：

Oxford Nanopore Technologies（ONT）长读长测序

原核生物基因组

bacterial genome assembly

初学者学习 ONT genome assembly workflow

核心分析流程为：

SeqKit
   ↓
fastplong
   ↓
LRGE
   ↓
Flye

后续可以在此基础上继续扩展：

QUAST
CheckM2
BUSCO
Genome annotation
Functional annotation