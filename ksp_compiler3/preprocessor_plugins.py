# preprocessor_plugins.py
# Written by Sam Windell
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version:
# http://www.gnu.org/licenses/gpl-2.0.html
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.


#=================================================================================================
# IDEAS:
#	-	+= -=
#	-	UI functions to receive arguments in any order: set_bounds(slider, width := 50, x := 20)

# BUG: commas in strings in list blocks. Can't replicate it?


import re
import collections
import ksp_compiler

#=================================================================================================
# Regular expressions
var_prefix_re = r"[%!@$]"

string_or_placeholder_re =  r'({\d+}|\"[^"]*\")'
varname_re_string = r'((\b|[$%!@])[0-9]*[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_0-9]+)*)\b'
variable_or_int = r"[^\]]+"

commas_not_in_parenth = re.compile(r",(?![^\(\)\[\]]*[\)\]])") # All commas that are not in parenthesis.
list_add_re = re.compile(r"^\s*list_add\s*\(")

# 'Regular expressions for 'blocks'
for_re = re.compile(r"^((\s*for)(\(|\s+))")
end_for_re = re.compile(r"^\s*end\s+for")
while_re = re.compile(r"^((\s*while)(\(|\s+))")
end_while_re = re.compile(r"^\s*end\s+while")
if_re = re.compile(r"^\s*if(\s+|\()")
end_if_re = re.compile(r"^\s*end\s+if")
init_re = r"^\s*on\s+init"

pers_keyword = "pers" # The keyword that will make a variable persistent.
read_keyword = "read" # The keyword that will make a variable persistent and then read the persistent value.
concat_syntax = "concat" # The name of the function to concat arrays.

multi_dim_ui_flag = " { UI ARRAY }"

ui_type_re = r"(?<=)(ui_button|ui_switch|ui_knob|ui_label|ui_level_meter|ui_menu|ui_slider|ui_table|ui_text_edit|ui_waveform|ui_value_edit)(?=\s)"
keywords_re = r"(?<=)(declare|const|" + pers_keyword + "|" + read_keyword + "|polyphonic|list)(?=\s)"

any_pers_re = r"(%s\s+|%s\s+)" % (pers_keyword, read_keyword)
pers_re = r"\b%s\b" % pers_keyword
read_re = r"\b%s\b" % read_keyword


#=================================================================================================
# This function is called before the macros have been expanded.
def pre_macro_functions(lines):
	remove_print(lines)
	handle_define_literals(lines)
	handle_define_lines(lines)
	handle_iterate_macro(lines)
	handle_literate_macro(lines)

# This function is called after the macros have been expanded.
def post_macro_functions(lines):
	incrementor(lines)
	handle_const_block(lines)
	handle_ui_arrays(lines)
	inline_declare_assignment(lines)
	multi_dimensional_arrays(lines)
	find_list_block(lines)
	calculate_open_size_array(lines)
	handle_lists(lines)
	variable_persistence_shorthand(lines)
	ui_property_functions(lines)
	expand_string_array_declaration(lines)	
	handle_array_concatenate(lines)
	# for line_obj in lines:
	# 	print(line_obj.command)

# Take the original deque of line objects, and for every new line number, add in the line_inserts.
def replace_lines(lines, line_nums, line_inserts):
	new_lines = collections.deque() # Start with an empty deque and build it up.
	# Add the text from the start of the file to the first line number we want to insert at.
	for i in range(0, line_nums[0] + 1):
		new_lines.append(lines[i])

	# For each line number insert any additional lines.
	for i in range(len(line_nums)):
		new_lines.extend(line_inserts[i])
		# Append the lines between the line_nums.
		if i + 1 < len(line_nums):
			for ii in range(line_nums[i] + 1, line_nums[i + 1] + 1):
				new_lines.append(lines[ii])

	# Add the text from the last line_num to the end of the document.
	for i in range(line_nums[len(line_nums) - 1] + 1, len(lines)):
		new_lines.append(lines[i])

	# Replace lines with new lines.
	for i in range(len(lines)):
		lines.pop()
	lines.extend(new_lines)	

def simplify_maths_addition(string):
	parts = string.split("+")
	count = 0
	while count < len(parts) - 1:
		try:
			# simplified = eval(parts[count] + "+" + parts[count+1])
			simplified = int(parts[count]) + int(parts[count+1])

			parts[count] = str(simplified)
			parts.remove(parts[count + 1])
		except:
			count += 1
			pass
	return("+".join(parts))

#=================================================================================================
# Remove print functions when the activate_logger() is not present.
def remove_print(lines):
	print_line_numbers = []
	logger_active_flag = False
	for i in range(len(lines)):
		line = lines[i].command
		if re.search(r"^\s*activate_logger\s*\(", line):
			logger_active_flag = True
		if re.search(r"^\s*print\s*\(", line):
			print_line_numbers.append(i)

	if not logger_active_flag:
		for i in range(len(print_line_numbers)):
			lines[print_line_numbers[i]].command = ""

def incrementor(lines):
	start_keyword = "START_INC"
	end_keyword = "END_INC"
	names = []
	it_vals = []
	step = []

	for i in range(len(lines)):
		line = lines[i].command
		m = re.search(r"^\s*%s\s*\(" % start_keyword, line)
		if m:
			mm = re.search(r"^\s*%s\s*\(\s*%s\s*\,\s*(.+)s*\,\s*(.+)\s*\)" % (start_keyword, varname_re_string), line)
			if mm:
				lines[i].command = ""
				names.append(mm.group(1))
				it_vals.append(eval(mm.group(4)))
				step.append(eval(mm.group(5)))
			else:
				raise ksp_compiler.ParseException(lines[i], "Incorrect parameters. Expected: START_INC(<name>, <literal-num-or-define>, <literal-num-or-define>)\n")	
		elif re.search(r"^\s*%s" % end_keyword, line):
			lines[i].command = ""
			names.pop()
			it_vals.pop()
			step.pop()
		elif names:
			for j in range(len(names)):
				mm = re.search(r"\b%s\b" % names[j], line)
				if mm:
					# lines[i].command = line.replace(names[j], str(it_vals[j]))
					lines[i].command = re.sub(r"\b%s\b" % names[j], str(it_vals[j]), lines[i].command)
					it_vals[j] += step[j]
					

# Function for concatenating multi arrays into one. 
def handle_array_concatenate(lines):
	line_numbers = []
	parent_array = []
	child_arrays = []
	num_args     = []
	init_line_num = None

	for i in range(len(lines)):
		line = lines[i].command
		if re.search(init_re, line):
			init_line_num = i
		m = re.search(r"(^\s*declare\s+)?%s\s*(\[(.*)\])?\s*:=\s*%s\s*\(([^\)]*)" % (varname_re_string, concat_syntax), line)
		if m:
			search_list = m.group(7).split(",")
			# Why doesn't this work? It seems to make makes all previous lists in child_arrays empty. Extend seems to work, but
			# append doesn't. This has been bodged for now.
			# child_arrays.append(search_list)
			# print(child_arrays)
			child_arrays.extend(search_list)
			parent_array.append(m.group(2))
			num_args.append(len(search_list))
			line_numbers.append(i)
			size = None
			if re.search(r"\bdeclare\b", line):
				if not m.group(5):
					raise ksp_compiler.ParseException(lines[i], "No array size given. Leave brackets [] empty to have the size auto generated.\n")	
				if not m.group(6):
					sizes = []
					for j in range(0, i):
						line2 = lines[j].command
						for arg in search_list:
							try: # The regex doesn't like it when there are [] or () in the arg list.
								mm = re.search(r"^\s*declare\s+%s?%s\s*(\[.*\])" % (var_prefix_re, arg.strip()), line2)
								if mm:
									sizes.append(mm.group(1))
									search_list.remove(arg)
									break
							except:
								raise ksp_compiler.ParseException(lines[i], "Syntax error.\n") 
					if search_list:  # If everything was found, then the list will be empty.
						raise ksp_compiler.ParseException(lines[i], "Undeclared array(s) in %s function: %s\n" % (concat_syntax, ', '.join(search_list).strip()))
					size = simplify_maths_addition(re.sub(r"[\[\]]", "", '+'.join(sizes)))
				else:
					size = m.group(6)
				lines[i].command = "declare %s[%s]" % (m.group(2), size) 
			else:
				lines[i].command = ""

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []
			
			# We have to calculate the start and end points in the arg list, because the append isn't working.
			s = 0
			if i != 0:
				for j in range(i):
					s += num_args[j]

			offsets = ["0"]
			for j in range(s, s + num_args[i]):
				offsets.append("num_elements(%s)" % child_arrays[j])

			add_offset = ""
			if num_args[i] != 1:
				add_offset = " + concat_offset"
				added_lines.append(lines[line_numbers[i]].copy("concat_offset := 0"))

			offset_command = "concat_offset := concat_offset + #offset#"
			template_text = [
			"for concat_it := 0 to num_elements(#arg#)-1",
			"	#parent#[concat_it%s] := #arg#[concat_it]" % add_offset,
			"end for"]

			for j in range(num_args[i]):
				if j != 0 and num_args[i] != 1:
					current_text = offset_command.replace("#offset#", offsets[j])
					added_lines.append(lines[line_numbers[i]].copy(current_text))
				for text in template_text:
					current_text = text.replace("#arg#", child_arrays[s + j]).replace("#parent#", parent_array[i])
					added_lines.append(lines[line_numbers[i]].copy(current_text))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

		# Add declare variables at the start on the init callback.
		new_lines = collections.deque()
		for i in range(0, init_line_num + 1):
			new_lines.append(lines[i])

		new_lines.append(lines[init_line_num].copy("	declare concat_it"))
		new_lines.append(lines[init_line_num].copy("	declare concat_offset"))
		for i in range(init_line_num + 1, len(lines)):
			new_lines.append(lines[i])

		for i in range(len(lines)):
			lines.pop()
		lines.extend(new_lines)	




# Create multidimensional arrays. 
# This functions replaces the multidimensional array declaration with a property with appropriate
# get and set functions to be sorted by the compiler further down the line.
def multi_dimensional_arrays(lines):
	dimensions = []
	num_dimensions = []
	name = []
	line_numbers = []

	for i in range(len(lines)):
		line = lines[i].command.strip()
		m = re.search(r"^\s*declare\s+" + any_pers_re + "?" + varname_re_string + "\s*\[" + variable_or_int + "\s*(,\s*" + variable_or_int + "\s*)+\]", line)
		if m:
			variable_name = m.group(2)
			prefix = m.group(3)
			if prefix:
				variable_name = variable_name[1:]
			else:
				prefix = ""

			dimensions_split = line[line.find("[") + 1 : line.find("]")].split(",") 
			num_dimensions.append(len(dimensions_split))
			dimensions.append(dimensions_split)

			line_numbers.append(i)

			underscore = ""
			if multi_dim_ui_flag in line:
				line = line.replace(multi_dim_ui_flag, "")
			else:
				underscore = "_"
			name.append(underscore + variable_name.strip())
			new_text = line.replace(variable_name, prefix + underscore + variable_name)
			new_text = new_text.replace("[", "[(").replace("]", ")]").replace(",", ")*(")
			lines[i].command = new_text
			
	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []
	
			for ii in range(num_dimensions[i]):
				current_text = "declare const " + name[i][1:] + ".SIZE_D" + str(ii + 1) + " := " + dimensions[i][ii]
				added_lines.append(lines[line_numbers[i]].copy(current_text))

			# start property
			current_text = "property " + name[i][1:]
			added_lines.append(lines[i].copy(current_text))

			# start get function
			# it might look something like this: function get(v1, v2, v3) -> result
			current_text = "function get(v1"
			for ii in range(1, num_dimensions[i]):
				current_text = current_text + ", v" + str(ii + 1) 
			current_text = current_text + ") -> result"
			added_lines.append(lines[i].copy(current_text))

			# get function body
			current_text = "result := " + name[i] + "["
			for ii in range(num_dimensions[i]):
				if ii != num_dimensions[i] - 1: 
					for iii in range(num_dimensions[i] - 1, ii, -1):
						current_text = current_text + dimensions[i][iii] + " * "
				current_text = current_text + "v" + str(ii + 1)
				if ii != num_dimensions[i] - 1:
					current_text = current_text + " + "
			current_text = current_text + "]"
			added_lines.append(lines[i].copy(current_text))

			# end get function
			added_lines.append(lines[i].copy("end function"))

			# start set function
			# it might look something like this: function set(v1, v2, v3, val)
			current_text = "function set(v1"
			for ii in range(1, num_dimensions[i]):
				current_text = current_text + ", v" + str(ii + 1) 
			current_text = current_text + ", val)"
			added_lines.append(lines[i].copy(current_text))

			# set function body
			current_text = name[i] + "["
			for ii in range(num_dimensions[i]):
				if ii != num_dimensions[i] - 1: 
					for iii in range(num_dimensions[i] - 1, ii, -1):
						current_text = current_text + dimensions[i][iii] + " * "
				current_text = current_text + "v" + str(ii + 1)
				if ii != num_dimensions[i] - 1:
					current_text = current_text + " + "
			current_text = current_text + "] := val"
			added_lines.append(lines[i].copy(current_text))

			# end set function
			added_lines.append(lines[i].copy("end function"))
			# end property
			added_lines.append(lines[i].copy("end property"))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

# Handle the new property functions.
def ui_property_functions(lines):
	# These can be easily changed.
	ui_control_properties = [
	"set_slider_properties(ui-id, default, picture, mouse_behaviour)",
	"set_switch_properties(ui-id, text, picture, text_alignment, font_type, textpos_y)",
	"set_label_properties(ui-id, text, picture, text_alignment, font_type, textpos_y)",
	"set_menu_properties(ui-id, picture, font_type, text_alignment, textpos_y)",
	"set_table_properties(ui-id, bar_color, zero_line_color)",
	"set_button_properties(ui-id, text, picture, text_alignment, font_type, textpos_y)",
	"set_level_meter_properties(ui-id, bg_color, off_color, on_color, overload_color)",
	"set_waveform_properties(ui-id, bar_color, zero_line_color)",
	"set_knob_properties(ui-id, text, default)",
	"set_bounds(ui-id, x, y, width, height)"
	]

	ui_func_names = []
	ui_func_args = []
	ui_func_size = []

	for ui_func in ui_control_properties:
		m = re.search(r"^\s*\w*", ui_func)
		ui_func_names.append(m.group(0))
		m = re.search(r"(?<=ui\-id,).*(?=\))", ui_func)
		arg_list = m.group(0).replace(" ", "").split(",")
		ui_func_args.append(arg_list)
		ui_func_size.append(len(arg_list))

	line_numbers = []
	prop_numbers = []
	var_names = []
	num_params = []
	params = []

	for i in range(len(lines)):
		line = lines[i].command.strip()
		for ii in range(len(ui_func_names)):
			if re.search(r"^\s*" + ui_func_names[ii] + r"\s*\(", line):
				comma_sep = line[line.find("(") + 1 : len(line) - 1].strip()
				line_numbers.append(i)
				prop_numbers.append(ii)

				string_list = re.split(commas_not_in_parenth, comma_sep)
				variable_name = string_list[0]
				var_names.append(variable_name)
				param_list = string_list[1:]

				params.append(param_list)
				num_params.append(len(param_list))
				if len(param_list) > ui_func_size[ii]:
					raise ksp_compiler.ParseException(lines[i], "Too many arguments, expected %d, got %d.\n" % (ui_func_size[ii], len(param_list)))
				elif len(param_list) == 0:
					raise ksp_compiler.ParseException(lines[i], "Function requires at least 2 arguments.\n")
				lines[i].command = ""

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			sum_max = 0			
			for ii in range(0, prop_numbers[i]):
				sum_max += ui_func_size[ii]
			for ii in range(num_params[i]):
				current_text = var_names[i] + " -> " + ui_func_args[prop_numbers[i]][ii] + " := " + params[i][ii]
				added_lines.append(lines[line_numbers[i]].copy(current_text))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

# When a variable is declared and initialised on the same line, check to see if the value needs to be
# moved over to the next line.
def inline_declare_assignment(lines):
	line_numbers = []
	var_text = []

	for i in range(len(lines)):
		line = lines[i].command.strip()
		m = re.search(r"^\s*declare\s+(polyphonic|%s|%s|global|local)?\s*%s\s*:=" % (pers_keyword, read_keyword, varname_re_string), line)
		if m and not re.search(r"\b%s\s*\(" % concat_syntax, line):
			int_flag = False
			value = line[line.find(":=") + 2 :]
			if not re.search(string_or_placeholder_re, line):
				try:
					eval(value)
					int_flag = True
				except:
					pass

			if not int_flag:
				pre_assignment_text = line[: line.find(":=")]
				variable_name = m.group(2)
				line_numbers.append(i)
				var_text.append(variable_name + " " + line[line.find(":=") :])
				lines[i].command = pre_assignment_text

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			added_lines.append(lines[line_numbers[i]].copy(var_text[i]))	

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

# Handle const blocks. Constants are replaced by declare const. If they are not assigned a value, 
# they will be equal to the previous const in the list + 1.
def handle_const_block(lines):
	start_line_num = None
	num_elements = None
	const_block = False
	current_val = None
	const_block_name = None
	current_assignment_list = []
	line_numbers = []
	array_size_text = []

	for i in range(len(lines)):
		line = lines[i].command
		m = re.search(r"^\s*const\s+" + varname_re_string, line) 
		if m:
			const_block = True
			lines[i].command = "declare " + m.group(1) + "[]"
			const_block_name = m.group(1)
			start_line_num = i
			current_val = "0"
			num_elements = 0
			current_assignment_list = []
			line_numbers.append(i)
		elif re.search(r"^\s*end\s+const", line):
			const_block = False

			assignment_text = "("
			for ii in range(len(current_assignment_list)):
				assignment_text = assignment_text + current_assignment_list[ii]
				if not ii == len(current_assignment_list) - 1:
					assignment_text = assignment_text + ", "
			assignment_text = assignment_text + ")"

			try:
				eval(num_elements)
			except:
				pass

			size_declaration = "declare const " + const_block_name + ".SIZE := " + str(num_elements)
			array_size_text.append(size_declaration)
			lines[start_line_num].command = lines[start_line_num].command.replace("]", str(num_elements) + "]")
			lines[start_line_num].command = lines[start_line_num].command + " := " + assignment_text

			lines[i].command = ""
		elif const_block and not line.strip() == "":
			assignment_text = current_val
			text = line.strip()
			if ":=" in line:
				assignment_text = line[line.find(":=") + 2 :]
				text = line[: line.find(":=")].strip()

			lines[i].command = "declare const " + const_block_name + "." + text + " := " + assignment_text
			current_assignment_list.append(current_val)
			current_val = simplify_maths_addition(assignment_text + "+1")
			try:
				eval(current_val)
			except:
				pass
			num_elements += 1

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			added_lines.append(lines[line_numbers[i]].copy(array_size_text[i]))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

# Handle list blocks. The list block is converted to list_add() commands for the regular list function
# to deal with them further down the line.
def find_list_block(lines):

	list_block = False
	list_name = None
	line_numbers = []
	new_list_add_text = []
	index = 0
	is_matrix = False

	for i in range(len(lines)):
		line = lines[i].command
		m = re.search(r"^\s*list\s*%s\s*(?:\[(%s)?\])?" % (varname_re_string, variable_or_int), line)
		if m:
			index = 0
			list_block = True
			list_name = m.group(1)
			if m.group(4):
				is_matrix = "," in m.group(4)
			# lines[i].command = "declare list " + list_name + "[]"
			lines[i].command = "declare " + lines[i].command
		elif list_block and not line.strip() == "":
			if re.search(r"^\s*end\s+list", line):
				list_block = False
				lines[i].command = ""
			else:
				string_list = re.search(commas_not_in_parenth, lines[i].command)
				if not string_list or not is_matrix:
					lines[i].command = "list_add(" + list_name + ", " + lines[i].command + ")"
				else:
					new_name = list_name + str(index)
					lines[i].command = "declare %s[] := (%s)" % (new_name, lines[i].command)
					line_numbers.append(i)
					new_list_add_text.append("list_add(" + list_name + ", " + new_name + ")")
				index += 1

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			added_lines.append(lines[line_numbers[i]].copy(new_list_add_text[i]))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)		

def find_all_arrays(lines):
	array_names = []
	array_sizes = []
	for i in range(len(lines)):
		line = lines[i].command
		m = re.search(r"^\s*declare\s+%s?%s\s*(?:\[(%s)\])" % (any_pers_re, varname_re_string, variable_or_int), line)
		if m:
			array_names.append(re.sub(var_prefix_re, "", m.group(2)))
			array_sizes.append(m.group(5))

	return (array_names, array_sizes)

# Convert lists and list_add() into commands that Kontakt can understand.
def handle_lists(lines):
	list_names   = []
	line_numbers = []
	init_flag    = None
	loop_flag    = None
	iterators    = []
	is_matrix    = []
	init_line_num = None

	matrix_size_lists = []
	matrix_list_add_line_nums = []
	matrix_list_add_text = []
	matrix_list_flag = "{MATRIX_LIST_ADD}"

	list_add_array_template = [
	"for list_it := 0 to #size# - 1",
	"	#list#[list_it + #offset#] := #arr#[list_it]",
	"end for"]
	list_add_array_tokens = ["#size#", "#list#", "#offset#", "#arr#"]

	def replace_tokens(template, tokens, values):
		new_text = []
		for text in template:
			for i in range(len(tokens)):
				text = text.replace(tokens[i], str(values[i]))
			new_text.append(text)
		return new_text

	list_matrix_template = [
	"declare #list#.sizes[#size#] := (#sizeList#)",
	"declare #list#.pos[#size#] := (#posList#)",
	"property #list#",
	"	function get(d1, d2) -> result",
	"		result := _#list#[#list#.pos[d1] + d2]",
	"	end function",
	"	function set(d1, d2, val)",
	"		_#list#[#list#.pos[d1] + d2] := val",
	"	end function",
	"end property"]
	list_matrix_tokens = ["#list#", "#size#", "#sizeList#", "#posList#"]

	array_names, array_sizes = find_all_arrays(lines)
	# print(array_names)

	for i in range(len(lines)):
		line = lines[i].command
		# m = re.search(r"^\s*declare\s+%s?list\s*%s" % (any_pers_re, varname_re_string), line)
		m = re.search(r"^\s*declare\s+%s?list\s*%s\s*(?:\[(%s)?\])?" % (any_pers_re, varname_re_string, variable_or_int), line)		
		if re.search(r"^\s*on\s+init", line):
			init_flag = True
			init_line_num = i
		elif re.search(r"^\s*end\s+on", line):
			if init_flag:
				for ii in range(len(iterators)):
					list_declare_line = lines[line_numbers[ii]].command
					square_bracket_pos = list_declare_line.find("[]") 
					lines[line_numbers[ii]].command = list_declare_line[: square_bracket_pos + 1] + str(iterators[ii]) + "]"
				init_flag = False
		elif re.search(for_re, line) or re.search(while_re, line) or re.search(if_re, line):
			loop_flag = True
		elif re.search(end_for_re, line) or re.search(end_while_re, line) or re.search(end_if_re, line):
			loop_flag = False
		elif m:
			name = m.group(2)
			is_pers = ""
			if m.group(1):
				is_pers = " " + m.group(1)
			line_numbers.append(i)
			iterators.append("0")

			is_matrix_type = False
			if m.group(5):
				is_matrix_type = "," in m.group(5)
				if is_matrix_type:
					prefix = ""
					if m.group(3):
						prefix = m.group(3)
					name = prefix + "_" + re.sub(var_prefix_re, "", name)

			list_names.append(name)
			is_matrix.append(is_matrix_type)

			# The number of elements is populated once the whole init callback is scanned.
			lines[i].command = "declare " + is_pers + name + "[]"
		else:
			if re.search(list_add_re, line):
				find_list_name = False
				for ii in range(len(list_names)):
					list_title = re.sub(var_prefix_re, "", list_names[ii])
					if is_matrix[ii]:
						list_title = list_title[1:]
					if re.search(r"list_add\s*\(\s*%s?%s\b" % (var_prefix_re, list_title), line):
						find_list_name = True
						if loop_flag:
							raise ksp_compiler.ParseException(lines[i], "list_add() cannot be used in loops or if statements.\n")
						if not init_flag:
							raise ksp_compiler.ParseException(lines[i], "list_add() can only be used in the init callback.\n")

						value = line[line.find(",") + 1 : len(line) - 1].strip()
						value = re.sub(var_prefix_re, "", value)

						size = None
						def increase_iterator(amount):
							iterators[ii] = simplify_maths_addition(iterators[ii] + " + " + str(amount))
							return amount	

						if not is_matrix[ii] or (is_matrix[ii] and not value in array_names):
							lines[i].command = list_names[ii] + "[" + str(iterators[ii]) + "] := " + value
							size = increase_iterator(1)
						else:
							array_location = array_names.index(value)
							new_text = replace_tokens(list_add_array_template, list_add_array_tokens, [array_sizes[array_location], "_" + list_title, iterators[ii], value])
							matrix_list_add_text.append(new_text)
							matrix_list_add_line_nums.append(i)
							lines[i].command = matrix_list_flag
							size = increase_iterator(array_sizes[array_location])						
						if is_matrix[ii]:
							matrix_size_lists.append([list_title, size])
						break
				if not find_list_name:
					undeclared_name = line[line.find("(") + 1 : line.find(",")].strip()
					raise ksp_compiler.ParseException(lines[i], undeclared_name + " had not been declared.\n") 

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			size_list = []
			list_name = re.sub(var_prefix_re, "", list_names[i])
			if is_matrix[i]:
				list_name = list_name[1:]
				pos_list = ["0"]
				for j in range(len(matrix_size_lists)):
					if matrix_size_lists[j][0] == list_name:
						size_list.append(str(matrix_size_lists[j][1]))
				size_counter = "0"
				for j in range(len(size_list)-1):
					size_counter = simplify_maths_addition(size_counter + "+" + size_list[j])
					pos_list.append(size_counter)
				new_text = replace_tokens(list_matrix_template, list_matrix_tokens, [list_name, str(len(size_list)), ", ".join(size_list), ", ".join(pos_list)])
				for text in new_text:
					added_lines.append(lines[line_numbers[i]].copy(text))	

			current_text = "declare const " + list_name + ".SIZE := " + str(len(size_list))
			added_lines.append(lines[line_numbers[i]].copy(current_text))

			line_inserts.append(added_lines)

		replace_lines(lines, line_numbers, line_inserts)

		# Add declare variables at the start on the init callback.
		new_lines = collections.deque()
		for i in range(0, init_line_num + 1):
			new_lines.append(lines[i])

		new_lines.append(lines[init_line_num].copy("	declare list_it"))
		for i in range(init_line_num + 1, len(lines)):
			new_lines.append(lines[i])

		for i in range(len(lines)):
			lines.pop()
		lines.extend(new_lines)

	if matrix_list_add_line_nums:
		line_inserts = collections.deque()
		line_nums = []
		for i in range(len(lines)):
			if lines[i].command == matrix_list_flag:
				lines[i].command = ""
				line_nums.append(i)

		for i in range(len(line_nums)):
			added_lines = []

			text_list = matrix_list_add_text[i]
			for text in text_list:
				added_lines.append(lines[line_nums[i]].copy(text))

			line_inserts.append(added_lines)
		replace_lines(lines, line_nums, line_inserts)

		
# When an array size is left with an open number of elements, use the list of initialisers to provide the array size.
# Const variables are also generated for the array size. 
def calculate_open_size_array(lines):
	array_name = []
	line_numbers = []
	num_ele = []

	for i in range(len(lines)):
		line = lines[i].command
		ls_line = re.sub(r"\s", "", line)
		m = re.search(r"^\s*declare\s+%s?%s\s*\[\s*\]\s*:=\s*\(" % (any_pers_re, varname_re_string), line)		
		if m:
			comma_sep = ls_line[ls_line.find("(") + 1 : len(ls_line) - 1]
			string_list = re.split(commas_not_in_parenth, comma_sep)
			num_elements = len(string_list)
			# name = line[: line.find("[")].replace("declare", "").strip()
			name = m.group(2)
			name = re.sub(var_prefix_re, "", name)

			lines[i].command = line[: line.find("[") + 1] + str(num_elements) + line[line.find("[") + 1 :]

			array_name.append(name)
			line_numbers.append(i)
			num_ele.append(num_elements)

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			current_text = "declare const " + array_name[i] + ".SIZE := " + str(num_ele[i])
			added_lines.append(lines[line_numbers[i]].copy(current_text))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

# Convert the single-line list of strings to one string per line for Kontakt to understand.
def expand_string_array_declaration(lines):
	string_var_names = []
	strings = []
	line_numbers = []
	num_ele = []

	for i in range(len(lines)):
		line = lines[i].command.strip()
		# Convert text array declaration to multiline
		m = re.search(r"^\s*declare\s+" + varname_re_string + r"\s*\[\s*" + variable_or_int + r"\s*\]\s*:=\s*\(\s*" + string_or_placeholder_re + r"(\s*,\s*" + string_or_placeholder_re + r")*\s*\)", line)
		if m:
			if m.group(2) == "!":
				comma_sep = line[line.find("(") + 1 : len(line) - 1]
				string_list = re.split(commas_not_in_parenth, comma_sep)
				num_elements = len(string_list)
				
				search_obj = re.search(r'\s+!' + varname_re_string, line)
				string_var_names.append(search_obj.group(0))

				num_ele.append(num_elements)
				strings.append(string_list)
				line_numbers.append(i)
			else:
				raise ksp_compiler.ParseException(lines[i], "Expected integers, got strings.\n")

	# For some reason this doesn't work in the loop above...?
	for lineno in line_numbers: 
		lines[lineno].command = lines[lineno].command[: lines[lineno].command.find(":")]

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			for ii in range(num_ele[i]):
				current_text = string_var_names[i] + "[" + str(ii) + "] := " + strings[i][ii] 
				added_lines.append(lines[line_numbers[i]].copy(current_text))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

# Handle the variable persistence shorthands.
def variable_persistence_shorthand(lines):
	line_numbers = []
	variable_names = []
	is_read = []

	for i in range(len(lines)):
		line = lines[i].command.strip()
		m = re.search(r"^\s*declare\s+" + any_pers_re, line)
		if m:
			is_read.append(read_keyword in m.group(1))
			variable_name = line
			variable_name = re.sub(ui_type_re, "", variable_name)
			variable_name = re.sub(keywords_re, "", variable_name)

			if variable_name.find("[") != -1:
				variable_name = variable_name.replace(variable_name[variable_name.find("[") : ], "")
			if variable_name.find("(") != -1:
				variable_name = variable_name.replace(variable_name[variable_name.find("(") : ], "")
			if variable_name.find(":=") != -1:
				variable_name = variable_name.replace(variable_name[variable_name.find(":=") : ], "")

			variable_names.append(variable_name.strip())
			line_numbers.append(i)
			lines[i].command = lines[i].command.replace(m.group(1), "")

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			current_text = "make_persistent(" + variable_names[i] + ")"
			added_lines.append(lines[line_numbers[i]].copy(current_text))
			if is_read[i]:
				current_text = "read_persistent_var(" + variable_names[i] + ")"
				added_lines.append(lines[line_numbers[i]].copy(current_text))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

# Create a list of macro calls based on the iterate macro start and end values.
def handle_iterate_macro(lines):
	min_val = []
	max_val = []
	step_val = []
	macro_name = []
	line_numbers = []
	downto = []
	is_single_line = []

	for index in range(len(lines)):
		line = lines[index].command
		if re.search(r"^\s*iterate_macro\s*\(", line):
			m = re.search(r"^\s*iterate_macro\s*\((.+)\)\s*(:=.+)", line)
			try:
				name = m.group(1)
				params = m.group(2)

				find_n = False
				if "#n#" in name:
					find_n = True
				is_single_line.append(find_n)

				if "downto" in params:
					to_stmt = "downto"
					downto.append(True)
				elif "to" in params:
					to_stmt = "to"
					downto.append(False)

				minv = eval(params[params.find(":=") + 2 : params.find(to_stmt)])
				if "step" in params:
					step = eval(params[params.find("step") + 4 :])
					maxv = eval(params[params.find(to_stmt) + len(to_stmt) : params.find("step")])
				else:
					step = 1
					maxv = eval(params[params.find(to_stmt) + len(to_stmt) :])

				if (minv > maxv and to_stmt == "to") or (minv < maxv and to_stmt == "downto"):
					raise ksp_compiler.ParseException(lines[index], "Min and max values are incorrectly weighted (For example, min > max when it should be min < max)./n")

			except:
				raise ksp_compiler.ParseException(lines[index], ""\
					"Incorrect values in iterate_macro statement.\n\nNormal 'declare const' variables cannot be used here, "\
					"instead a 'define' const or literal must be used. The macro you are iterating must have only have 1 integer parameter, "\
					"this will be replaced by the values in the chosen range.\n")

			macro_name.append(name)
			min_val.append(minv)
			max_val.append(maxv)
			step_val.append(step)
			line_numbers.append(index)

			lines[index].command = ""

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			step = int(step_val[i])
			offset = 1
			if downto[i]:
				step = -step
				offset = -1

			for ii in range(int(min_val[i]), int(max_val[i]) + offset, step):
				current_text = macro_name[i] + "(" + str(ii) + ")"
				if is_single_line[i]:
					current_text = macro_name[i].replace("#n#", str(ii))
				added_lines.append(lines[line_numbers[i]].copy(current_text))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

def handle_literate_macro(lines):
	literal_vals = []
	macro_name = []
	line_numbers = []
	is_single_line = []

	for index in range(len(lines)):
		line = lines[index].command
		if re.search(r"^\s*literate_macro\(", line):
			name = line[line.find("(") + 1 : line.find(")")]
			params = line[line.find(")") + 1:]

			find_n = False
			if "#l#" in name:
				find_n = True
			is_single_line.append(find_n)

			try:
				literal = params[params.find("on") + 2 : ].strip()

			except:
				raise ksp_compiler.ParseException(lines[index], "Incorrect values in literate_macro statement. " + \
						"The macro you are iterating must have only have 1 string parameter, this will be replaced by the value of the defined literal.\n")

			if len(literal):
				macro_name.append(name)
				literal_vals.append(literal.split(","))
				line_numbers.append(index)

			lines[index].command = re.sub(r'[^\r\n]', '', line)

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			for ii in literal_vals[i]:
				current_text = macro_name[i] + "(" + str(ii) + ")"
				if is_single_line[i]:
					current_text = macro_name[i].replace("#l#", str(ii))
				added_lines.append(lines[line_numbers[i]].copy(current_text))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)

# Find all define literal declarations and then scan the document and replace all occurrences with their value.
# define command's have no scope, they are completely global at the moment.
def handle_define_literals(lines):
	define_titles = []
	define_values = []
	define_line_pos = []
	for index in range(len(lines)):
		line = lines[index].command 
		if re.search(r"^\s*define\s+literals\s+", line):
			if re.search(r"^\s*define\s+literals\s+" + varname_re_string + r"\s*:=", line):
				text_without_define = re.sub(r"^\s*define\s+literals\s*", "", line)
				colon_bracket_pos = text_without_define.find(":=")

				# before the assign operator is the title
				title = text_without_define[ : colon_bracket_pos].strip()
				define_titles.append(title)

				# after the assign operator is the value
				value = text_without_define[colon_bracket_pos + 2 : ].strip()
				m = re.search("^\((([a-zA-Z_][a-zA-Z0-9_.]*)?(\s*,\s*[a-zA-Z_][a-zA-Z0-9_.]*)*)\)$", value)
				if not m:
					raise ksp_compiler.ParseException(lines[index], "Syntax error in define literals: Comma separated identifier list in () expected.\n")

				value = m.group(1)
				define_values.append(value)

				define_line_pos.append(index)
				# remove the line
				lines[index].command = re.sub(r'[^\r\n]', '', line)
			else:
				raise ksp_compiler.ParseException(lines[index], "Syntax error in define literals.\n")

	# if at least one define const exsists
	if define_titles:
		# scan the code can replace any occurances of the variable with it's value
		for line_obj in lines:
			line = line_obj.command 
			for index, item in enumerate(define_titles):
				if re.search(r"\b" + item + r"\b", line):
					# character_before = line[line.find(item) - 1 : line.find(item)]  
					# if character_before.isalpha() == False and character_before.isdiget() == False:  
					line_obj.command = line_obj.command.replace(item, str(define_values[index]))

# Find all define declarations and then scan the document and replace all occurrences with their value.
# define command's have no scope, they are completely global at the moment. There is some hidden define
# functionality... you can use define as a text substitution macro by wrapping the value in #.
def handle_define_lines(lines):
	define_titles = []
	define_values = []
	define_line_pos = []
	for index in range(len(lines)):
		line = lines[index].command 
		if re.search(r"^\s*define\s+", line):
			if re.search(r"^\s*define\s+" + varname_re_string + r"\s*:=", line):
				text_without_define = re.sub(r"^\s*define\s*", "", line)
				colon_bracket_pos = text_without_define.find(":=")

				# before the assign operator is the title
				title = text_without_define[ : colon_bracket_pos].strip()
				define_titles.append(title)

				# after the assign operator is the value
				value = text_without_define[colon_bracket_pos + 2 : ].strip()
				define_values.append(value)

				define_line_pos.append(index)
				# remove the line
				lines[index].command = re.sub(r'[^\r\n]', '', line)
			else:
				raise ksp_compiler.ParseException(lines[index], "Syntax error in define.\n")

	# If at least one define const exists.
	if define_titles:
		# Check each of the values to see if they contain any other define consts.
		for i in range(len(define_values)):
			for ii in range(len(define_titles)):
				if define_titles[ii] in define_values[i]:
					define_values[i] = define_values[i].replace(define_titles[ii], define_values[ii])

		# Do any maths if needed.
		for i in range(len(define_values)):
			try:
				if not re.search(r"^#.*#$", define_values[i]):
					define_values[i] = re.sub(r"\s+mod\s+", " % ", define_values[i])
					define_values[i] = eval(define_values[i])
				else:
					define_values[i] = define_values[i][1 : len(define_values[i]) - 1]
			except:
				raise ksp_compiler.ParseException(lines[define_line_pos[i]], "Undeclared variable in define statement.\n")

		# Scan the code and replace any occurrences of the name with it's value.
		for line_obj in lines:
			line = line_obj.command 
			for index, item in enumerate(define_titles):
				if re.search(r"\b" + item + r"\b", line):
					line_obj.command = line_obj.command.replace(item, str(define_values[index]))

# For each UI array declaration, create a list of 'declare ui_control' lines and the UI ID of each to an array.
def handle_ui_arrays(lines):
	ui_declaration = []
	variable_names = []
	line_numbers = []
	num_elements = []
	pers_text = []
	multidimensional = []

	# Find all of the array declarations.
	for index in range(len(lines)):
		line = lines[index].command 
		ls_line = line.lstrip()
		m = re.search(r"^\s*declare\s+" + any_pers_re + "?" + ui_type_re + "\s*" + varname_re_string + "\s*\[[^\]]+\]", ls_line)
		if m:
			is_pers = m.group(1)
			ui_type = m.group(2).strip()
			var_name = m.group(3).strip()
			variable_name = re.sub(var_prefix_re, "", var_name)

			# Check that if it is a table, it is actually an array.
			proceed = True
			if ui_type == "ui_table":
				if not re.search(r"\[[^\]]+\]\s*\[", ls_line):
					proceed = False

			if proceed:
				array_size = ls_line[ls_line.find("[") + 1 : ls_line.find("]")]
				is_multi_dimensional = "," in array_size
				underscore = ""
				if is_multi_dimensional:
					underscore = "_"
				# string_between_brackets = "(" + array_size.replace(",", ")*(") + ")"
				string_between_brackets = 1
				dimension_list = array_size.split(",")
				for dimension in dimension_list:
					try:
						string_between_brackets = string_between_brackets * int(eval(dimension))
					except:
						raise ksp_compiler.ParseException(lines[index], "Invalid number of elements. Native 'declare const' variables cannot be used here, instead a 'define' const or a literal must be used.\n")			
				num_element = string_between_brackets
				# try:
				# 	num_element = eval(string_between_brackets)
				# 	print("BETWEEN:@ " + str(num_element))
				# 	print("BETWEEN TEXT:  " + string_between_brackets)
				# except:
				# 	raise ksp_compiler.ParseException(lines[index], "Invalid number of elements. Native 'declare const' variables cannot be used here, instead a 'define' const or a literal must be used.\n")			

				pers_text.append(is_pers)
				# if there are parameters
				if "(" in ls_line:
					if ui_type == "ui_table":
						first_close_bracket = ls_line.find("]") + 1
						table_elements = ls_line[ls_line.find("[", first_close_bracket) + 1 : ls_line.find("]", first_close_bracket)]
						ui_declaration.append("declare " + ui_type + " " + underscore + var_name + "[" + table_elements + "]" + ls_line[ls_line.find("(") : ls_line.find(")") + 1]) 
					else:
						ui_declaration.append("declare " + ui_type + " " + underscore + var_name + ls_line[ls_line.find("(") : ls_line.find(")") + 1]) 
				else:
					ui_declaration.append("declare " + ui_type + " " + underscore + var_name) 
				line_numbers.append(index)
				num_elements.append(num_element)
				if is_multi_dimensional:
					variable_name = "_" + variable_name
				variable_names.append(variable_name)
				lines[index].command  = "declare " + variable_name + "[" + str(array_size) + "]"
				if is_multi_dimensional:
					lines[index].command = lines[index].command + multi_dim_ui_flag

	if line_numbers:
		line_inserts = collections.deque()
		for i in range(len(line_numbers)):
			added_lines = []

			num_eles = int(num_elements[i])

			for ii in range(0, num_eles):
				if "(" in ui_declaration[i]:
					if "[" in ui_declaration[i]:
						parameter_start = ui_declaration[i].find("[")
					else:
						parameter_start = ui_declaration[i].find("(")
					current_text = ui_declaration[i][:parameter_start] + str(ii) + ui_declaration[i][parameter_start:]
				else:
					current_text = ui_declaration[i] + str(ii)
				if pers_text[i]:
					current_text = current_text.strip()
					current_text = current_text[: 7] + " " + pers_text[i] + " " + current_text[8 :]

				# Add individual UI declaration.
				added_lines.append(lines[line_numbers[i]].copy(current_text))

				# Add ID to array.
				add_to_array_text = variable_names[i] + "[" + str(ii) + "]" + " := get_ui_id(" + variable_names[i] + str(ii) + ")"
				added_lines.append(lines[i].copy(add_to_array_text))

			line_inserts.append(added_lines)
		replace_lines(lines, line_numbers, line_inserts)
