'use client';

import React from 'react';
import * as Select from '@radix-ui/react-select';
import { Check, ChevronDown } from 'lucide-react';

interface CategoryFilterProps {
  categories: string[];
  selectedCategory: string | null;
  onCategoryChange: (category: string | null) => void;
  label?: string;
}

export function CategoryFilter({
  categories,
  selectedCategory,
  onCategoryChange,
  label = 'Filter by Category',
}: CategoryFilterProps) {
  const handleValueChange = (value: string) => {
    if (value === 'all') {
      onCategoryChange(null);
    } else {
      onCategoryChange(value);
    }
  };

  return (
    <div className="w-full sm:w-64">
      <label htmlFor="category-filter" className="block text-sm font-medium text-gray-700 mb-2">
        {label}
      </label>
      <Select.Root
        value={selectedCategory || 'all'}
        onValueChange={handleValueChange}
      >
        <Select.Trigger
          id="category-filter"
          className="inline-flex items-center justify-between w-full px-4 py-2.5 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[44px]"
          aria-label={label}
        >
          <Select.Value />
          <Select.Icon>
            <ChevronDown className="h-4 w-4 text-gray-500" aria-hidden="true" />
          </Select.Icon>
        </Select.Trigger>

        <Select.Portal>
          <Select.Content
            className="overflow-hidden bg-white rounded-lg shadow-lg border border-gray-200 z-50"
            position="popper"
            sideOffset={5}
          >
            <Select.Viewport className="p-1">
              <Select.Item
                value="all"
                className="relative flex items-center px-8 py-2.5 text-sm text-gray-900 rounded-md outline-none cursor-pointer select-none hover:bg-blue-50 focus:bg-blue-50 data-[state=checked]:bg-blue-100 min-h-[44px]"
              >
                <Select.ItemIndicator className="absolute left-2 inline-flex items-center">
                  <Check className="h-4 w-4 text-blue-600" aria-hidden="true" />
                </Select.ItemIndicator>
                <Select.ItemText>All Categories</Select.ItemText>
              </Select.Item>

              {categories.map((category) => (
                <Select.Item
                  key={category}
                  value={category}
                  className="relative flex items-center px-8 py-2.5 text-sm text-gray-900 rounded-md outline-none cursor-pointer select-none hover:bg-blue-50 focus:bg-blue-50 data-[state=checked]:bg-blue-100 min-h-[44px]"
                >
                  <Select.ItemIndicator className="absolute left-2 inline-flex items-center">
                    <Check className="h-4 w-4 text-blue-600" aria-hidden="true" />
                  </Select.ItemIndicator>
                  <Select.ItemText>{category}</Select.ItemText>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </div>
  );
}
