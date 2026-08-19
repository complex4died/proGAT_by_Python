#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


FASTQ_SUFFIXES = (".fastq.gz", ".fq.gz", ".fastq", ".fq")

# 保留 notebook 中原来的默认环境/数据库位置。
# 如实际路径发生变化，可直接修改这里。
CONDA_PATH = Path("/opt/homebrew/Caskroom/miniconda/base/envs/proGAT")
DATABASE_DIR = Path("/Users/latterday/Desktop/Project/proGAT/database")
THREADS = 8


def parse_args():
    parser = argparse.ArgumentParser(
        description="proGAT ONT prokaryotic genome assembly and QC pipeline"
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="输入数据文件夹，文件夹内放置 FASTQ/FASTQ.GZ 文件",
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="输出文件夹",
    )

    return parser.parse_args()


def sample_name_from_path(path: Path) -> str:
    """去除常见 FASTQ 扩展名并返回样本名。"""
    name = path.name
    for suffix in FASTQ_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def get_fastq_files(input_dir: Path):
    """获取输入目录中的 FASTQ 文件。"""
    files = [
        p for p in input_dir.iterdir()
        if p.is_file() and p.name.endswith(FASTQ_SUFFIXES)
    ]
    return sorted(files)


def run_command(command, stdout_file=None):
    """统一运行外部命令并在终端打印。"""
    print("\n[RUN]", " ".join(map(str, command)), flush=True)

    if stdout_file is None:
        subprocess.run(command, check=True)
    else:
        stdout_file.parent.mkdir(parents=True, exist_ok=True)
        with stdout_file.open("w") as fh:
            subprocess.run(command, stdout=fh, check=True, text=True)


def check_program(program):
    if shutil.which(program) is None:
        raise RuntimeError(f"找不到程序: {program}，请检查 PATH 或环境是否已激活。")


def run_seqkit_stats(samples, output_dir):
    print("\n========== 1. SeqKit stats ==========")
    outdir = output_dir / "seqkit_stats"
    outdir.mkdir(parents=True, exist_ok=True)

    for input_file in samples:
        sample_name = sample_name_from_path(input_file)
        outfile = outdir / f"{sample_name}_stats.txt"
        run_command(
            ["seqkit", "stats", str(input_file), "-a", "-T"],
            stdout_file=outfile,
        )


def run_fastplong(samples, output_dir):
    print("\n========== 2. fastplong filter ==========")
    outdir = output_dir / "fastplong_filtered"
    outdir.mkdir(parents=True, exist_ok=True)

    fastplong_bin = CONDA_PATH / "bin" / "fastplong"
    if not fastplong_bin.exists():
        # 如果固定 conda 路径不存在，则尝试当前 PATH
        fastplong = shutil.which("fastplong")
        if fastplong is None:
            raise RuntimeError(
                f"找不到 fastplong。已检查 {fastplong_bin} 和当前 PATH。"
            )
        fastplong_bin = Path(fastplong)

    for input_file in samples:
        sample_name = sample_name_from_path(input_file)
        sample_output_dir = outdir / sample_name
        sample_output_dir.mkdir(parents=True, exist_ok=True)

        output_fastq = sample_output_dir / f"{sample_name}_filtered.fastq.gz"
        output_html = sample_output_dir / f"{sample_name}_fastplong.html"
        output_json = sample_output_dir / f"{sample_name}_fastplong.json"

        run_command([
            str(fastplong_bin),
            "-i", str(input_file),
            "-o", str(output_fastq),
            "-h", str(output_html),
            "-j", str(output_json),
        ])

    return outdir


def run_lrge(samples, fastplong_dir, output_dir):
    print("\n========== 3. LRGE genome size estimation ==========")
    outdir = output_dir / "lrge"
    outdir.mkdir(parents=True, exist_ok=True)
    docker_image = "staphb/lrge:latest"

    for sample in samples:
        sample_name = sample_name_from_path(sample)
        input_file = fastplong_dir / sample_name / f"{sample_name}_filtered.fastq.gz"
        output_name = f"{sample_name}_size.txt"

        run_command([
            "docker", "run", "--rm",
            "--platform", "linux/amd64",
            "-v", f"{input_file.resolve()}:/input.fastq.gz:ro",
            "-v", f"{outdir.resolve()}:/output",
            docker_image,
            "lrge",
            "-P", "ont",
            "-t", str(THREADS),
            "-o", f"/output/{output_name}",
            "/input.fastq.gz",
        ])

    return outdir


def run_flye(samples, fastplong_dir, output_dir):
    print("\n========== 4. Flye assembly ==========")
    outdir = output_dir / "flye"
    outdir.mkdir(parents=True, exist_ok=True)

    for sample in samples:
        sample_name = sample_name_from_path(sample)
        input_file = fastplong_dir / sample_name / f"{sample_name}_filtered.fastq.gz"
        sample_outdir = outdir / sample_name

        # 与 notebook 保持一致，目前 genome-size 固定为 5m。
        run_command([
            "flye",
            "--nano-hq", str(input_file),
            "--genome-size", "5m",
            "--out-dir", str(sample_outdir),
            "--threads", str(THREADS),
        ])

    return outdir


def run_assembly_seqkit(samples, flye_dir):
    print("\n========== 5. Assembly SeqKit stats ==========")

    for sample in samples:
        sample_name = sample_name_from_path(sample)
        assembly = flye_dir / sample_name / "assembly.fasta"
        run_command(["seqkit", "stats", str(assembly), "-a"])


def run_quast(samples, flye_dir, output_dir):
    print("\n========== 6. QUAST ==========")
    outdir = output_dir / "quast"
    outdir.mkdir(parents=True, exist_ok=True)
    docker_image = "staphb/quast:latest"

    for sample in samples:
        sample_name = sample_name_from_path(sample)
        input_file = flye_dir / sample_name / "assembly.fasta"

        run_command([
            "docker", "run", "--rm",
            "--platform", "linux/amd64",
            "-v", f"{input_file.resolve()}:/input.fasta:ro",
            "-v", f"{outdir.resolve()}:/output",
            docker_image,
            "quast.py",
            "/input.fasta",
            "-o", f"/output/{sample_name}_quast",
        ])


def run_checkm2(samples, flye_dir, output_dir):
    print("\n========== 7. CheckM2 ==========")
    outdir = output_dir / "checkm"
    outdir.mkdir(parents=True, exist_ok=True)
    docker_image = "staphb/checkm2:latest"

    database_file = (
        DATABASE_DIR
        / "checkm2"
        / "CheckM2_database"
        / "uniref100.KO.1.dmnd"
    )

    if not database_file.exists():
        raise FileNotFoundError(f"CheckM2 数据库不存在: {database_file}")

    for sample in samples:
        sample_name = sample_name_from_path(sample)
        input_file = flye_dir / sample_name / "assembly.fasta"

        run_command([
            "docker", "run", "--rm",
            "--platform", "linux/amd64",
            "-v", f"{input_file.resolve()}:/input.fasta:ro",
            "-v", f"{outdir.resolve()}:/output",
            "-v", f"{database_file.resolve()}:/checkm_data.dmnd:ro",
            docker_image,
            "checkm2", "predict",
            "--threads", str(THREADS),
            "--input", "/input.fasta",
            "--output-directory", f"/output/{sample_name}_checkm2",
            "--database", "/checkm_data.dmnd",
        ])


def prepare_busco_database():
    print("\n========== 8. Prepare BUSCO database ==========")

    busco_db = DATABASE_DIR / "busco"
    busco_db.mkdir(parents=True, exist_ok=True)
    lineage_dir = busco_db / "bacteria_odb12" / "lineages" / "bacteria_odb12"

    # 避免每次运行脚本都重复下载数据库。
    if lineage_dir.exists():
        print(f"BUSCO database already exists: {lineage_dir}")
        return busco_db

    run_command([
        "docker", "run", "--rm",
        "--platform", "linux/amd64",
        "-v", f"{busco_db.resolve()}:/busco_db",
        "staphb/busco:latest",
        "busco", "--download", "bacteria_odb12",
        "--download_path", "/busco_db/bacteria_odb12",
    ])

    return busco_db


def run_busco(samples, flye_dir, output_dir, busco_db):
    print("\n========== 9. BUSCO ==========")

    outdir = output_dir / "BUSCO"
    outdir.mkdir(parents=True, exist_ok=True)
    docker_image = "staphb/busco:latest"
    busco_db_temp = busco_db / "bacteria_odb12" / "lineages"

    if not busco_db_temp.exists():
        raise FileNotFoundError(f"BUSCO lineage 目录不存在: {busco_db_temp}")

    for sample in samples:
        sample_name = sample_name_from_path(sample)
        input_file = flye_dir / sample_name / "assembly.fasta"
        sample_output_dir = outdir / sample_name
        sample_output_dir.mkdir(parents=True, exist_ok=True)

        run_command([
            "docker", "run", "--rm",
            "--platform", "linux/amd64",
            "-v", f"{input_file.resolve()}:/input.fasta:ro",
            "-v", f"{sample_output_dir.resolve()}:/output",
            "-v", f"{busco_db_temp.resolve()}:/busco_db:ro",
            docker_image,
            "busco",
            "-i", "/input.fasta",
            "-o", "/busco_result",
            "--out_path", "/output",
            "-l", "/busco_db/bacteria_odb12",
            "-m", "genome",
            "--cpu", str(THREADS),
            "--offline",
            "-f",
        ])


def main():
    args = parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    if not input_dir.is_dir():
        print(f"错误：输入目录不存在或不是文件夹: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    samples = get_fastq_files(input_dir)
    if not samples:
        print(
            f"错误：{input_dir} 中没有找到 FASTQ 文件。支持: {', '.join(FASTQ_SUFFIXES)}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Input directory : {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Samples         : {len(samples)}")
    for sample in samples:
        print(f"  - {sample.name}")

    # 运行前检查 notebook 中直接依赖 PATH 的程序。
    check_program("seqkit")
    check_program("flye")
    check_program("docker")

    try:
        run_seqkit_stats(samples, output_dir)
        fastplong_dir = run_fastplong(samples, output_dir)
        run_lrge(samples, fastplong_dir, output_dir)
        flye_dir = run_flye(samples, fastplong_dir, output_dir)
        run_assembly_seqkit(samples, flye_dir)
        run_quast(samples, flye_dir, output_dir)
        run_checkm2(samples, flye_dir, output_dir)
        busco_db = prepare_busco_database()
        run_busco(samples, flye_dir, output_dir, busco_db)
    except subprocess.CalledProcessError as exc:
        print(f"\n流程终止：命令运行失败，返回码 {exc.returncode}", file=sys.stderr)
        sys.exit(exc.returncode or 1)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"\n流程终止：{exc}", file=sys.stderr)
        sys.exit(1)

    print("\n========== proGAT pipeline completed ==========")


if __name__ == "__main__":
    main()