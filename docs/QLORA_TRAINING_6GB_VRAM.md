# Hướng Dẫn Huấn Luyện QLoRA 4-bit Cho GPU 6GB VRAM (NVIDIA RTX 3050 Laptop)

Tài liệu kỹ thuật chi tiết về kiến trúc và cách chạy script `scripts/train_qlora.py` trong dự án **AI-Office**, được tinh chỉnh đặc thù cho GPU 6GB VRAM nhằm huấn luyện mô hình suy luận chuỗi tư duy (Synthetic Reasoning Chain-of-Thought) có thẻ `<think> ... </think>`.

---

## 1. Phân Bổ Ngân Sách Bộ Nhớ (VRAM Budget Analysis)

| Thành phần | Dung lượng ước tính (Qwen2.5-3B) | Dung lượng ước tính (Qwen2.5-7B) | Cơ chế tối ưu |
| :--- | :--- | :--- | :--- |
| **Trọng số Base Model** | ~2,100 MiB (2.05 GB) | ~4,200 MiB (4.10 GB) | `BitsAndBytesConfig` 4-bit NormalFloat (nf4) + Double Quantization |
| **LoRA Adapter (r=16, alpha=32)** | ~45 MiB | ~85 MiB | Chỉ huấn luyện các ma trận low-rank trên 7 module tuyến tính (`q, k, v, o, gate, up, down`) |
| **Trạng thái Optimizer** | ~95 MiB | ~180 MiB | `paged_adamw_8bit` (tự động phân trang sang CPU RAM khi có đỉnh tải đột biến) |
| **Kích hoạt (Activations)** | ~1,100 MiB | ~1,100 MiB | `gradient_checkpointing=True` (`use_reentrant=False`), `batch_size=1`, `max_seq_length=2048` |
| **Tổng đỉnh VRAM ước tính** | **~3,340 MiB (~3.26 GB)** | **~5,565 MiB (~5.43 GB)** | **An toàn tuyệt đối trên RTX 3050 6GB Laptop!** |

> [!TIP]
> - Đối với GPU 6GB Laptop (với Windows Desktop chiếm khoảng 800 - 1,200 MiB VRAM), mô hình **`Qwen/Qwen2.5-3B-Instruct`** là lựa chọn hoàn hảo nhất với biên độ an toàn hơn 1.8 GB VRAM trống.
> - Nếu sử dụng **`Qwen/Qwen2.5-Coder-7B-Instruct`**, nên giảm `--context_length` xuống `1536` hoặc tắt bớt ứng dụng đồ họa (Steam, Wallpaper Engine, Chrome).

---

## 2. Cài Đặt Môi Trường Huấn Luyện

Chạy trong môi trường Python 3.10 - 3.13 hỗ trợ CUDA:

```cmd
# 1. Cài đặt PyTorch với CUDA 12.4+
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 2. Cài đặt các thư viện PEFT, TRL, BitsAndBytes
pip install -r requirements-train.txt
```

---

## 3. Các Lệnh Huấn Luyện Chính

### 3.1. Kiểm tra cấu hình và dataset (Dry Run / Pre-flight Check)
Trước khi chạy hàng giờ trên GPU, chạy `--dry_run` để thẩm định bộ nhớ, phân tích cấu trúc dataset và kiểm tra thẻ `<think>`:
```cmd
python scripts/train_qlora.py --dry_run
```

### 3.2. Huấn luyện QLoRA chuẩn trên 6GB VRAM
```cmd
python scripts/train_qlora.py ^
    --model_id "Qwen/Qwen2.5-3B-Instruct" ^
    --data_path "data/training/reasoning_cot_train.jsonl" ^
    --output_dir "models/qlora-reasoning-adapter" ^
    --batch_size 1 ^
    --grad_accum 8 ^
    --context_length 2048 ^
    --epochs 3 ^
    --learning_rate 2e-4 ^
    --lora_r 16 ^
    --lora_alpha 32 ^
    --logging_steps 5 ^
    --save_steps 50
```

### 3.3. Huấn luyện và tự động Merge trọng số Base Model
```cmd
python scripts/train_qlora.py ^
    --model_id "Qwen/Qwen2.5-3B-Instruct" ^
    --data_path "data/training/reasoning_cot_train.jsonl" ^
    --output_dir "models/qlora-reasoning-adapter" ^
    --merge_and_save ^
    --merged_output_dir "models/merged-reasoning-qwen"
```

---

## 4. Chuyển Đổi Sang GGUF & Nạp Vào Ollama

Sau khi quá trình huấn luyện hoàn tất, các file Modelfile và hướng dẫn được tự động tạo tại `models/qlora-reasoning-adapter/`:

### Cách 1: Nạp trực tiếp LoRA Adapter vào Ollama (Nhanh nhất)
Ollama hỗ trợ nạp adapter trực tiếp qua lệnh `ADAPTER`:
```cmd
python scripts/export_to_ollama.py --create_in_ollama
```
Hoặc thủ công:
```cmd
ollama create reasoning-office -f models/qlora-reasoning-adapter/Modelfile.reasoning-office
ollama run reasoning-office "Một hồ nước có 1 cụm hoa bèo, mỗi ngày nhân đôi..."
```

### Cách 2: Merge và Convert sang GGUF (Tối ưu tốc độ suy luận)
1. Dùng `llama.cpp` để chuyển model đã merge sang GGUF 16-bit:
   ```cmd
   python F:\llama.cpp\convert_hf_to_gguf.py "models/merged-reasoning-qwen" --outtype f16 --outfile "models/reasoning-model-f16.gguf"
   ```
2. Lượng tử hóa sang `Q4_K_M` (tiết kiệm VRAM khi chạy Ollama):
   ```cmd
   llama-quantize "models/reasoning-model-f16.gguf" "models/reasoning-model-q4_k_m.gguf" q4_k_m
   ```
3. Tạo file Modelfile trỏ tới file GGUF và nạp vào Ollama:
   ```dockerfile
   FROM ./models/reasoning-model-q4_k_m.gguf
   PARAMETER temperature 0.2
   PARAMETER stop "<|im_end|>"
   SYSTEM """You are Claude Office Reasoning Assistant..."""
   ```
   ```cmd
   ollama create reasoning-office -f Modelfile
   ```

---

## 5. Các Kỹ Thuật Chống OOM (Out-of-Memory) Đã Triển Khai

1. **`BitsAndBytes` 4-bit NF4 with Double Quantization**: Giảm 75% kích thước trọng số gốc mà không làm suy giảm chất lượng biểu diễn.
2. **`Gradient Checkpointing` (`use_reentrant=False`)**: Giải phóng toàn bộ các tensor kích hoạt trung gian trong lượt lan truyền thuận (forward pass) và tính toán lại khi lan truyền ngược (backward pass), tiết kiệm ~65% VRAM kích hoạt.
3. **`Paged AdamW 8-bit`**: Sử dụng công nghệ Unified Memory của CUDA để tự động đẩy trạng thái optimizer sang RAM hệ thống khi GPU chạm ngưỡng giới hạn.
4. **`Micro Batch Size = 1` + `Gradient Accumulation = 8`**: Đạt hiệu quả huấn luyện của batch size = 8 nhưng chỉ tiêu thụ VRAM của 1 sample duy nhất tại một thời điểm.
5. **Giới hạn `Context Length = 2048`**: Cắt tỉa các mẫu quá dài để giữ độ phức tạp bộ nhớ tự chú ý (self-attention) ở mức kiểm soát được.
6. **PyTorch Allocator Configuration**: Khởi tạo biến môi trường `PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"` ngăn hiện tượng phân mảnh bộ nhớ CUDA trên Windows.
