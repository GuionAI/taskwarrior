#!/usr/bin/env python3
"""Regenerate Formula/task.rb in the checked-out homebrew-tap directory."""
import os
import pathlib

version = os.environ["VERSION"]
repo = os.environ["REPO"]
sha_linux = os.environ["SHA_LINUX"]
sha_macos = os.environ["SHA_MACOS"]

formula = f'''class Task < Formula
  desc "A command-line todo list manager"
  homepage "https://github.com/{repo}"
  version "{version}"
  license "MIT"
  conflicts_with "go-task", because: "both install a 'task' binary"

  on_macos do
    on_arm do
      url "https://github.com/{repo}/releases/download/v{version}/task-{version}-aarch64-macos.tar.gz"
      sha256 "{sha_macos}"
    end
  end

  on_linux do
    on_intel do
      url "https://github.com/{repo}/releases/download/v{version}/task-{version}-x86_64-linux.tar.gz"
      sha256 "{sha_linux}"
    end
  end

  def install
    bin.install "task"
    bash_completion.install "completions/task.sh"
    zsh_completion.install "completions/_task"
    fish_completion.install "completions/task.fish"
  end

  test do
    system bin/"task", "--version"
  end
end
'''

out = pathlib.Path("tap/Formula/task.rb")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(formula)
print(f"Written {out}")
