#include <assert.h>
#include <stdio.h>

#include <algorithm>

#include "sudoku.h"

int board[N];
int spaces[N];
int nspaces;
int (*chess)[COL] = (int (*)[COL])board;

static void find_spaces()
{
  nspaces = 0;
  for (int cell = 0; cell < N; ++cell) {
    if (board[cell] == 0)
      spaces[nspaces++] = cell;
  }
}

void input(const char in[N])
{
  for (int cell = 0; cell < N; ++cell) {
    board[cell] = in[cell] - '0';
    assert(0 <= board[cell] && board[cell] <= NUM);
  }
  find_spaces();
}

bool available(int guess, int cell)
{
  for (int i = 0; i < NEIGHBOR; ++i) {
    int neighbor = neighbors[cell][i];
    if (board[neighbor] == guess) {
      return false;
    }
  }
  return true;
}

bool solve_sudoku_basic(int which_space)
{
  if (which_space >= nspaces) { // 如果当前空间索引大于等于总空间数
    return true; // 返回true，表示解决成功
  }

  // find_min_arity(which_space);
  int cell = spaces[which_space]; // 获取当前空间索引对应的单元格

  for (int guess = 1; guess <= NUM; ++guess) { // 遍历1到NUM之间的所有可能值
    if (available(guess, cell)) { // 如果当前值可用
      // hold
      assert(board[cell] == 0); // 断言当前单元格的值为0
      board[cell] = guess; // 将当前单元格的值设置为guess

      // try
      if (solve_sudoku_basic(which_space+1)) { // 递归调用solve_sudoku_basic函数，尝试解决下一个空间
        return true; // 返回true，表示解决成功
      }

      // unhold
      assert(board[cell] == guess); // 断言当前单元格的值为guess
      board[cell] = 0; // 将当前单元格的值设置为0
    }
  }
  return false; // 返回false，表示解决失败
}
