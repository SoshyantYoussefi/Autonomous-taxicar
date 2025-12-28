#include <iostream>
#include <utility>
#include <vector>
#include <map>
#include <string>
#include <queue>
#include <algorithm>

using namespace std;
using Node = pair<vector<string>, vector<string>>;

vector<string> path(vector<string> s, vector<string> t) {
    	map<string, vector<string>> row_net = {
		{"1", {"2", "3"}},
		{"2", {"1", "4", "5"}},
		{"3", {"1", "4", "6"}},
		{"4", {"2", "3", "5", "6"}},
		{"5", {"2", "4", "7"}},
		{"6", {"4", "3", "7"}},
		{"7", {"5", "6"}}
	};

	string start = s[0];
	string target = t[0];
    map<string, vector<string>> ns_cl_tb_1 = {
        {"7", {"6"}},
        {"2", {"4", "5"}},
        {"3", {"1"}},
        {"4", {"3", "6"}},
    };

    map<string, vector<string>> ns_cl_tb_2 = {
        {"7", {"5"}},
        {"2", {"1"}},
        {"3", {"6", "4"}},
        {"4", {"2", "5"}},
    };

    vector<string> not_start = (s[1] == "1") ? ns_cl_tb_1[start] : ns_cl_tb_2[start];
    vector<string> correct_last = (t[1] == "1") ? ns_cl_tb_1[target] : ns_cl_tb_2[target];

    vector<string> complete;

	queue<pair<string, vector<string>>> st;

	st.push({ start, {} });

	while (!st.empty()) {
        auto current = st.front();
        st.pop();

        string current_node = current.first;
        vector<string> visited_nodes = current.second;

        string previous = !visited_nodes.empty() ? visited_nodes.back() : "None";
        string pre_previous = visited_nodes.size() >= 2 ? visited_nodes[visited_nodes.size() -2] : "None";
        
        if (current_node == target && !visited_nodes.empty()) {
            if ((find(correct_last.begin(), correct_last.end(), previous) != correct_last.end())) {
                visited_nodes.push_back(current_node);
                complete = visited_nodes;
                break;   
            }
        }
        
        visited_nodes.push_back(current_node);

        for (const auto& neighbour : row_net[current_node]) {
            if ((find(not_start.begin(), not_start.end(), neighbour) != not_start.end()) && (visited_nodes.size() == 1)) {
                continue;
            }
            if (previous != neighbour && pre_previous != neighbour) {
                st.push({ neighbour, visited_nodes });
            }
        }
	}
	
	for (const auto& node : complete) {
        cout << "NODE: "<< node << endl;
    }

    return complete;
}

string invert_turn(const string& t) {
    if (t == "H") return "V";
    if (t == "V") return "H";

    return t;
}

vector<string> path_to_turns(vector<string> path) {
    vector<string> turns;
    map<string, vector<pair<string, vector<string>>>> turn_table = {
        {"1", { {"2", {"S"}}, {"3", {"S"}} }},
        {"2", { {"1", {"N"}}, {"5", {"V"}}, {"4", {"H", "S"}} }},
        {"3", { {"1", {"N"}}, {"4", {"V", "S"}}, {"6", {"H"}} }},
        {"4", { {"2", {"V", "S"}}, {"3", {"H", "S"}}, {"5", {"H"}}, {"6", {"V"}} }},
        {"5", { {"2", {"H", "S"}}, {"4", {"V", "S"}}, {"7", {"S"}} }},
        {"6", { {"4", {"H", "S"}}, {"3", {"V", "S"}}, {"7", {"S"}} }},
        {"7", { {"6", {"N"}}, {"5", {"N"}} }},
    };

    string start = path.front();
    path.erase(path.begin());

    string current = start;

    for (const auto& node : path) {
        if (node == "8") {
            turns.push_back("B");
            continue;
        }
        vector<pair<string, vector<string>>> pot_turns = turn_table[current];
        for (const auto& comp_node : pot_turns) {
            if (comp_node.first == node) {
                for (const auto& turn : comp_node.second){
                    turns.push_back(turn);
                }
                current = node;
                break;
            }
        }
    }

    vector<string> correct_turns;
    for (const auto& turn : turns) {
        if (turn != "N") {
            if (turn == "B") {
                correct_turns.pop_back();
            }
            correct_turns.push_back(turn);
        }
    }

    return correct_turns;
}

vector<string> full_algo(vector<string> stops) {
    vector<string> tot_stops;

    map<string, vector<string>> stop_to_grid = {
        {"A1", {"2", "1"}},
        {"A2", {"2", "2"}},
        {"B1", {"7", "1"}},
        {"B2", {"7", "2"}},
        {"C1", {"4", "1"}},
        {"C2", {"4", "2"}},
        {"D1", {"3", "1"}},
        {"D2", {"3", "2"}},
    };

    for (int i = 0; i < stops.size() - 1; i++) {
        vector<string> curr_node = stop_to_grid[stops[i]];
        vector<string> next_node = stop_to_grid[stops[i+1]];

        vector<string> segment = path(curr_node, next_node);
        segment.push_back("8");
        tot_stops.insert(tot_stops.end(), segment.begin(), segment.end());
    }
    return path_to_turns(tot_stops);
}

// int main()
// {
//     vector<string> p = full_algo({"A1", "B2", "C2"});

//     for (const auto& turn : p) {
//         cout << "turn: " << turn << endl;
//     }
// }

// Run program: Ctrl + F5 or Debug > Start Without Debugging menu
// Debug program: F5 or Debug > Start Debugging menu

// Tips for Getting Started: 
//   1. Use the Solution Explorer window to add/manage files
//   2. Use the Team Explorer window to connect to source control
//   3. Use the Output window to see build output and other messages
//   4. Use the Error List window to view errors
//   5. Go to Project > Add New Item to create new code files, or Project > Add Existing Item to add existing code files to the project
//   6. In the future, to open this project again, go to File > Open > Project and select the .sln file