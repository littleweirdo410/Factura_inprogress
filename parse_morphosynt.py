from dictionaries import *


def wf_to_dic(wf_string): # записываем словоформы-строки в виде словаря
    wf_profile = {}
    if len(wf_string) > 6 and wf_string.find('#') != 0:
        wf_data = wf_string[:len(wf_string)-1].split('\t')
        wf_data[3] = 'PTCPL' if 'VerbForm=Part' in wf_data[4] else wf_data[3]
        wf_profile.update({'idw': int(wf_data[0])})
        wf_profile.update({'wf': wf_data[1]})
        wf_profile.update({'nf': wf_data[2]})
        wf_profile.update({'pos': wf_data[3]})
        wf_profile.update({'xpos': '_'})
        wf_profile.update({'tags': wf_data[4]})
        wf_profile.update({'head_id': int(wf_data[5])}) if wf_data[5] != 'root' else wf_profile.update({'head_id': 0})
        wf_profile.update({'rel': wf_data[6]})
        wf_profile.update({'deps': '_'})
        wf_profile.update({'misc': '_'})
    return wf_profile


def stanza_to_ud(ind, l, sent): # берем номер строки, предложения в нем и само предложение и переводим его в формат ud
    itext, sent_len = sent.text, 0
    ud = '\n# ' + str(ind) + str(l) + ' ' + itext + '\n'
    for word in sent.words:
        sent_len += 1
    for i in range (0, sent_len):
        head = sent.words[i].head if word.head > 0 else "root"
        prop_set = (sent.words[i].id, sent.words[i].text, sent.words[i].lemma, sent.words[i].pos, sent.words[i].feats, head, sent.words[i].deprel)
        for k in prop_set:
            if k != "NoneType":
                ud = ud + str(k) + '\t'
            else:
                ud = ud + '-' + '\t'
        ud = ud + '\n'
    return ud.split('\n')


def trankit_to_ud(s):
    wf_profile = {}
    wf_profile.update({'idw': s['id']})
    wf_profile.update({'wf': s['text']})
    wf_profile.update({'nf': ''})
    wf_profile.update({'pos': s['upos']})
    wf_profile.update({'xpos': '_'})
    wf_profile.update({'tags': s['feats']}) if 'feats' in s.keys() else wf_profile.update({'tags': ''})
    wf_profile.update({'head_id': int(s['head'])}) if 'deprel' in s.keys() and s['deprel'] != 'root' else wf_profile.update({'head_id': 0})
    wf_profile.update({'rel': s['deprel']}) if 'deprel' in s.keys() else wf_profile.update({'rel': 'UNKNOWN'})
    wf_profile.update({'deps': '_'})
    wf_profile.update({'misc': '_'})
    return wf_profile


def sent_dict_from_sents(ind, l, sent, parse_w_stanza): # создаем для предложения словарь, в ключе - ID словоформы, в значении - словарь с UD-данными
    sent_w_dicts = {}
    if parse_w_stanza:
        sent_ud = stanza_to_ud(ind, l, sent)
        for wf in sent_ud:
            wf_as_dic = wf_to_dic(wf)
            if len(wf) > 1 and len(wf_as_dic):
                sent_w_dicts[wf_as_dic['idw']] = (wf_as_dic)
    else:
        for wf in sent:
            wf_as_dic = trankit_to_ud(wf)
            sent_w_dicts[wf_as_dic['idw']] = (wf_as_dic)
    return sent_w_dicts


def check_head(const, sent_w_dicts):
    correct, e_type = True, ''
    for k in const.keys():
        hlist, new_ch = set(const[k]), const[k]
        while len(new_ch) != 0 and k not in hlist:
            new_ch_tmp = []
            for a in new_ch:
                if a in const.keys():
                    new_ch_tmp.append(a)
            new_ch = []
            for m in new_ch_tmp:
                hlist = hlist.union(set(const[m]))
                new_ch = const[m]
        if k in hlist:
            correct, e_type = False, 'Cyclic heads '
            break
    for w in sent_w_dicts.values():
        if w['head_id'] == 0 and w['rel'] != 'root':
            correct, e_type = False, 'Root with wrong relation '
    return correct, e_type


def heads(sent_in_dics):
    head_ids = list(set([s['head_id'] for s in sent_in_dics if s['head_id'] != 0]))
    head_ids.sort()
    return head_ids


def rearrange_pp(sent_in_dics):
    for i, w in sent_in_dics.items():
        if w['pos'] == 'ADP' and w['head_id'] != 0:
            head_noun = sent_in_dics[w['head_id']]
            p_id, head_noun_id = w['idw'], sent_in_dics[w['head_id']]['idw']
            for s in sent_in_dics.values():
                if s['idw'] == sent_in_dics[w['head_id']]['head_id']:
                    noun_head_id = s['idw']
            head_noun['head_id'] = p_id
            w['head_id'] = noun_head_id if 'noun_head_id' in locals() else head_noun_id
    return sent_in_dics


def rearrange_cop(sent_in_dics):
    for i, w in sent_in_dics.items():
        cop, nom_pred = {}, {}
        if w['pos'] == 'AUX' and w['head_id'] != 0:
            nom_pred, cop = sent_in_dics[w['head_id']], w
            nom_pred['head_id'], nom_pred['rel'] = w['idw'], 'cop'
            w['head_id'], w['rel'] = 0, 'root'
    for i, dep in sent_in_dics.items():
        if len(cop) > 0 and len(nom_pred) > 0 and dep['head_id'] == nom_pred['idw'] and dep['rel'] in ['nsubj', 'advmod']:
            dep['head_id'] = cop['idw']
    return sent_in_dics


def find_children(heads, sent_in_dics):
    const, const_w = {}, {}
    for h in heads:
        children, ch_w = [], []
        for s in sent_in_dics.values():
            if s['head_id'] == h:
                children.append(s['idw'])
                ch_w.append(s['wf'])
        const.update({h: children})
        const_w.update({sent_in_dics[h]['wf']: ch_w})
    return const, const_w


#поиск скобок слева и справа для словоформ предложения:
def find_brackets_l(sent_w_dicts, const, h_terminals):
    brackets_l = {int(w['idw']): [] for w in sent_w_dicts.values()}
    for x, y in const.items():
        br_tmp, i = [x], x
        if y[0] < x and y[0] in const.keys():
            while const[i][0] in const.keys():
                i = const[i][0]
                if const[i][0] < i:
                    br_tmp.append(const[i][0])
                else:
                    br_tmp.append(i)
            brackets_l[min(br_tmp)].append(x)
        elif y[0] < x and y[0] not in const.keys():
            brackets_l[y[0]].append(x)
        elif y[0] > x:
            brackets_l[x].append(x)
    for w, h in brackets_l.items():
        if sent_w_dicts[w]['pos'] in h_terminals and w not in const.keys():
            h.append(sent_w_dicts[w]['idw'])
    return brackets_l


def find_brackets_r(sent_w_dicts, const, h_terminals):
    brackets_r = {int(w['idw']): [] for w in sent_w_dicts.values()}
    for x, y in const.items():
        br_tmp, i = [x], x
        if y[-1] > x and y[-1] in const.keys():
            while const[i][-1] in const.keys():
                i = const[i][-1]
                if const[i][-1] > i:
                    br_tmp.append(const[i][-1])
                else:
                    br_tmp.append(i)
            brackets_r[max(br_tmp)].append(x)
        elif y[-1] > x and y[-1] not in const.keys():
            brackets_r[y[-1]].append(x)
        elif y[-1] < x:
            brackets_r[x].append(x)
    for w, h in brackets_r.items():
        if sent_w_dicts[w]['pos'] in h_terminals and w not in const.keys():
            h.append(sent_w_dicts[w]['idw'])
    return brackets_r


def post_proc(brackets, sent_w_dicts, t): # removing empty items, ignoring punctuation
    if t == 0:
        for x, y in brackets.items():
            if sent_w_dicts[x]['rel'] == 'punct':
                for p in y:
                    if x + 1 in brackets.keys():
                        brackets[x + 1].append(p)
                brackets[x] = []
        for y in brackets.values():
            y.sort(reverse=True)

    if t == 1:
        for x, y in brackets.items():
            if sent_w_dicts[x]['rel'] == 'punct':
                for p in y:
                    brackets[x - 1].append(p)
                brackets[x] = []
        for y in brackets.values():
            y.sort()
    brackets = dict(filter(lambda elem: len(elem[1]) > 0, brackets.items()))
    return brackets


phrase_dict = {
    'NOUN': 'NP', 'PRON': 'NP', 'PROPN': 'NP', 'DET': 'NP', 'ADJ': 'AP', 'ADP': 'PP', 'ADV': 'AdvP', 'VERB': 'VP',
    'AUX': 'VP', 'CCONJ': 'CCONJP', 'INTJ': 'INTJP', 'NUM': 'NumP', 'PART': 'Particle', 'PUNCT': 'PUNCTP',
    'SCONJ': 'SCONJP', 'SYM': 'SYMP', 'X': 'XP', 'PTCPL': 'PartP'
}

def put_brackets_sent(brackets_l, brackets_r, sent_w_dicts, phrase_dict, delete_orth, selected_cons):
    sent_n_brackets = '' #'Structure=>\n'
    for x in sent_w_dicts.keys():
        if x in brackets_l.keys():
            for y in brackets_l[x]: 
                if phrase_dict[sent_w_dicts[y]['pos']] in selected_cons:
#                    sent_n_brackets = sent_n_brackets + '[' # wout. category label
                    sent_n_brackets = sent_n_brackets + ' [' + phrase_dict[sent_w_dicts[y]['pos']]
        sent_n_brackets = sent_n_brackets + ' ' + sent_w_dicts[x]['wf']
        if x in brackets_r.keys():
            for y in brackets_r[x]:
                if phrase_dict[sent_w_dicts[y]['pos']] in selected_cons:
                    sent_n_brackets = sent_n_brackets + ']'
    punc = '''!()—–−-;:'",.?@_«…»'''
    sent_n_brackets_clear = ""
    for ele in sent_n_brackets:
        if delete_orth and ele not in punc:
            sent_n_brackets_clear += ele
        elif not delete_orth:
            sent_n_brackets_clear += ele
    sent_n_brackets_clear = sent_n_brackets_clear.replace('  ', ' ')
    return sent_n_brackets_clear


def put_brackets_sent_compare(brackets_l, brackets_r, sent_w_dicts, phrase_dict, delete_orth, selected_cons_compare):
    sent_n_brackets = '' #'Structure=>\n'
    for x in sent_w_dicts.keys():
        if x in brackets_l.keys():
            for y in brackets_l[x]:
                if phrase_dict[sent_w_dicts[y]['pos']] in selected_cons_compare:
#                    sent_n_brackets = sent_n_brackets + '[' # wout. category label
                    sent_n_brackets = sent_n_brackets + ' [' + phrase_dict[sent_w_dicts[y]['pos']]
        sent_n_brackets = sent_n_brackets + ' ' + sent_w_dicts[x]['wf']
        if x in brackets_r.keys():
            for y in brackets_r[x]:
                if phrase_dict[sent_w_dicts[y]['pos']] in selected_cons_compare:
                    sent_n_brackets = sent_n_brackets + ']'
    punc = '''!()—–−-;:'",.?@_«…»'''
    sent_n_brackets_clear = ""
    for ele in sent_n_brackets:
        if delete_orth and ele not in punc:
            sent_n_brackets_clear += ele
        elif not delete_orth:
            sent_n_brackets_clear += ele
    sent_n_brackets_clear = sent_n_brackets_clear.replace('  ', ' ')
    return sent_n_brackets_clear


def select_spec_cons(brackets_l, brackets_r, sent_w_dicts, phrase_dict, selected_cons, emb):
    const_dict, cur_tags_dict, output, phr_dict, idc, phr_dict_ids = {}, {}, '', {}, 0, {}
    for sc in selected_cons:
        cur_tags = []
        for t, p in phrase_dict.items():
            if p == sc:
                cur_tags.append(t)
        cur_tags_dict[sc] = cur_tags
    for x, y in cur_tags_dict.items():
        const_dict[x] = {}
        for xl, yl in brackets_l.items():
            for l in yl:
                if sent_w_dicts[l]['pos'] in y:
                    const_dict[x][l] = [xl]
    for x, y in const_dict.items():
        for a, b in y.items():
            for xr, yr in brackets_r.items():
                if a in yr:
                    const_dict[x][a].append(xr)
    const_dict = {k: v for k, v in const_dict.items() if len(v) > 0}
    if not emb:
        for x, y in const_dict.items():
            emb_tmp = []
            for a in y.keys():
                checked = True
                for b in y.values():
                    if a >= b[0] and a <= b[1] and y[a] != b:
                        checked = False
                if checked:
                    emb_tmp.append(a)
            const_dict[x] = {k: v for k, v in y.items() if k in emb_tmp}
    for k, v in const_dict.items():
        output = output + k + ':\n'
        for h, st_fin in v.items():
            phrase, ids = '', []
            for l in range(st_fin[0], st_fin[1] + 1):
                output, phrase = output + sent_w_dicts[l]['wf'] + ' ', phrase + sent_w_dicts[l]['wf'] + ' '
                ids.append(l)
            phr_dict.update({idc : [k, h, phrase]})
            phr_dict_ids.update({idc : [k, h, ids]})
            idc += 1
            output = output + '\n'
        output = output + '\n'
    return output, phr_dict, phr_dict_ids  # {type1: [ {head1: [constituent1_start, constituent1_finish], [], ...}  ...], {head2: [...] } ...}
#{0: ['NP', 'Детская футбольная команда '], 1: ['NP', 'пещеру '], 2: ['NP', 'тренировки 23 июня '], 3: ['NP', 'июня '], 4: ['VP', 'Детская футбольная команда пошла в пещеру после тренировки 23 июня ']}
#{0: ['NP', [1, 2, 3]], 1: ['NP', [6]], 2: ['NP', [8, 9, 10]], 3: ['NP', [10]], 4: ['VP', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]]}


def create_json(sentence, sent_w_dicts, sent_parse, all_xps_txt, all_xps_dict, id, t, dlin, head_set, parse_w_stanza):
    dlin, new_sent, new_toks, new_cons, json_list = len(t.split(' ')), sentence.copy(), [], [], []
    source = 'S' if parse_w_stanza else 'U'
    new_sent['id'], new_sent['text'], new_sent['length'], new_sent['source'] = id, t, dlin, source
    new_sent['sentence_tree'] = sent_parse
    for i, word in sent_w_dicts.items():
        n_w, tagset = token.copy(), [word['pos']]
        n_w['itoken'], n_w['token'], n_w['lemma'], n_w['parent_token_index'], n_w['edge_type'] = word['idw'], word['wf'], word['nf'], word['head_id'], word['rel']
        for tag in word['tags'].split('|'):
            tagset.append(tag)
        n_w['tagsets'] = [tagset]
        n_w['constituent'], list_for_shortest = token['constituent'].copy(), {}
        if i in head_set:
            for k, val in all_xps_dict.items():
                if val[1] == i:
                    n_w['constituent']['name'], n_w['constituent']['is_head'], n_w['constituent']['id'] = val[0], True, k
        else:
#            n_w['constituent']['name'], n_w['constituent']['is_head'], n_w['constituent']['id'] = 'XP', False, 100500
            for ic, c in all_xps_dict.items():
                if i in c[2]:
                    list_for_shortest.update({ic: c[2]})
            if len(list_for_shortest):
                min_len = min(map(len, list_for_shortest.values()))
                for ic, c in all_xps_dict.items():
                    if len(all_xps_dict[ic][2]) == min_len and i in c[2]:
                        n_w['constituent']['name'], n_w['constituent']['is_head'], n_w['constituent']['id'] = c[0], False, ic
        new_toks.append(n_w)
    for i, c in all_xps_dict.items():
        n_c, tagset, tokens = constituent.copy(), [sent_w_dicts[c[1]]['pos']], []
        n_c["name"], n_c["id"], n_c["head_id"], n_c["length"] = c[0], i, sent_w_dicts[c[1]]['idw'], len(c[2])
        for tag in sent_w_dicts[c[1]]['tags'].split('|'):
            tagset.append(tag)
        n_c["tags"] = tagset
        for p in c[2]:
            tokens.append([p, sent_w_dicts[p]['wf']])
        n_c["tokens"] = tokens
        n_c["text"] = all_xps_txt[i][2]
        new_cons.append(n_c)
    new_sent['tokens'] = new_toks
    new_sent['constituents'] = new_cons
    json_list = new_sent
    return json_list


class set_params:
    def __init__(self, parse_w_stanza, delete_orth, xps, emb, h_terminals, selected_cons, selected_cons_compare):
        self.parse_w_stanza = parse_w_stanza # True when parser = Stanza, False - when UDPIPE, later turn this to params
        self.delete_orth = delete_orth # delete orthography from the final tree
        self.xps = xps # return specific phrases separately
        self.emb = emb # if xps - return subconstituents, not maximal projection
        self.h_terminals = h_terminals # terminals to be put in brackets w/out dependents
        self.selected_cons = selected_cons # for cases when we want only some specific constituents
        self.selected_cons_compare = selected_cons_compare # for cases when we want only some specific constituents


class write_json:
        
    def write_parsing(param, fin, verbosity):
        json_parse = []
        if param.parse_w_stanza:
            import stanza
            nlp = stanza.Pipeline('ru', processors='tokenize,pos,lemma,depparse')
        else:
            from trankit import Pipeline
            p = Pipeline(lang='russian', gpu=False, cache_dir='./cache')
        test, s_id = fin.read().split('\n'), 0
        for ind, t in enumerate(test):
            sents = nlp(t).sentences if param.parse_w_stanza else [p.posdep(t)['sentences'][0]['tokens']]
            for l, sent in enumerate(sents):
                print('Парсинг предложения: Абзац {}, предложение {}'.format(ind, l))            
                s_id = str(s_id) + '-' + str(l)
                sent_w_dicts = sent_dict_from_sents(ind, l, sent, param.parse_w_stanza)
                sent_in_dics = rearrange_cop(rearrange_pp(sent_w_dicts))
                head_set = heads(sent_w_dicts.values())
                const, const_w = find_children(head_set, sent_w_dicts)[0], find_children(head_set, sent_w_dicts)[1]
                sent_text = sent.text
                try:
                    if check_head(const, sent_w_dicts)[0]:
                        brackets_l = find_brackets_l(sent_w_dicts, const, param.h_terminals)
                        brackets_r = find_brackets_r(sent_w_dicts, const, param.h_terminals)
                        brackets_l = post_proc(brackets_l, sent_w_dicts, 0)
                        brackets_r = post_proc(brackets_r, sent_w_dicts, 1)
                        sent_parse = put_brackets_sent(brackets_l, brackets_r, sent_w_dicts, phrase_dict, param.delete_orth, param.selected_cons)
                        sent_parse_for_comparison = put_brackets_sent_compare(brackets_l, brackets_r, sent_w_dicts, phrase_dict, param.delete_orth, param.selected_cons_compare)
                        if param.xps:
                            all_xps_txt = select_spec_cons(brackets_l, brackets_r, sent_w_dicts, phrase_dict, param.selected_cons, param.emb)[1]
                            all_xps_dict = select_spec_cons(brackets_l, brackets_r, sent_w_dicts, phrase_dict, param.selected_cons, param.emb)[2]
                        if verbosity: print(sent_parse_for_comparison, "\n")
                        json_parse.append(create_json(sentence, sent_w_dicts, sent_parse, all_xps_txt, all_xps_dict, s_id, sent_text, 0, head_set, param.parse_w_stanza))
                    else:
                        print(const, check_head(const, sent_w_dicts)[1])
                except Exception as inst:
                    print(inst, type(inst), inst.args)
        return json_parse