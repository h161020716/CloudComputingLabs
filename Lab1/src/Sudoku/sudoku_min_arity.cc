#include <assert.h>

#include <algorithm>

#include "sudoku.h"

static int arity(int cell)
{
	bool occupied[10] = {false};
	for (int i = 0; i < NEIGHBOR; ++i)
	{
		int neighbor = neighbors[cell][i];
		occupied[board[neighbor]] = true;
	}
	return std::count(occupied + 1, occupied + 10, false);
}

static void find_min_arity(int space)
{
	int cell = spaces[space]; // 获取当前空间索引对应的单元格
	int min_space = space; // 最小空间索引	
	int min_arity = arity(cell); // 最小弧度

	for (int sp = space + 1; sp < nspaces && min_arity > 1; ++sp)
	{
		int cur_arity = arity(spaces[sp]); // 当前空间索引对应的弧度
		if (cur_arity < min_arity) // 如果当前弧度小于最小弧度
		{
			min_arity = cur_arity;
			min_space = sp;
		}
	}

	if (space != min_space)
	{
		std::swap(spaces[min_space], spaces[space]);
	}
}

bool solve_sudoku_min_arity(int which_space)
{
	if (which_space >= nspaces)
	{
		return true;
	}

	find_min_arity(which_space);	// 找到最小弧度
	int cell = spaces[which_space]; // 获取当前空间索引对应的单元格

	for (int guess = 1; guess <= NUM; ++guess)
	{ // 遍历1到NUM之间的所有可能值
		if (available(guess, cell))
		{ // 如果当前值可用
			// hold
			assert(board[cell] == 0); // 断言当前单元格的值为0
			board[cell] = guess;	  // 将当前单元格的值设置为guess

			// try
			if (solve_sudoku_min_arity(which_space + 1))
			{				 // 递归调用solve_sudoku_min_arity函数，尝试解决下一个空间
				return true; // 返回true，表示解决成功
			}

			// unhold
			assert(board[cell] == guess); // 断言当前单元格的值为guess
			board[cell] = 0;			  // 将当前单元格的值设置为0
		}
	}
	return false; // 返回false，表示解决失败
}
