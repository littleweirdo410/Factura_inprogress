import io
import yaml
import argparse
import os
import sys
import json


def parse(text, parser_cmd, tmp_dir):
    text_path = os.path.join(tmp_dir, 'fact_extractor__input_text.txt')
    with io.open(text_path, 'w', encoding='utf-8') as wrt:
        wrt.write('{}\n'.format(text))

    parsing_path = os.path.join(tmp_dir, 'fact_extractor__parsing.json')

    s = parser_cmd.replace('$input', text_path).replace('$output', parsing_path)
    r = os.system(s)
    assert(r == 0)
    return parsing_path


def extract_facts(parsing_path, extractor_cmd, tmp_dir):
    output_path = os.path.join(tmp_dir, 'fact_extractor__output.json')
    s = extractor_cmd.replace('$input', parsing_path).replace('$output', output_path)
    r = os.system(s)
    assert(r == 0)
    with open(output_path, 'r') as f:
        data = json.load(f)
    return data


class ExtractedFact:
    def __init__(self):
        self.fact_name = None
        self.subfact_name = None
        self.fact_text = None
        self.slots = dict()

    @staticmethod
    def load_json(fact_data):
        fact = ExtractedFact()
        fact.fact_name = fact_data['fact_name']
        fact.subfact_name = fact_data['subfact_name']
        fact.fact_text = fact_data['subfact_name']

        if 'slots' in fact_data:
            for slot_data in fact_data['slots']:
                slot_name = slot_data['name']
                slot_value = slot_data['text']
                fact.slots[slot_name] = slot_value

        return fact


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Fact extractor tester')
    parser.add_argument('--input', type=str, default='./tests/basic_tests.yaml', help='file with test descriptions')
    parser.add_argument('--output', type=str, default='./tmp/tests_report.txt')
    parser.add_argument('--tmp', type=str, default='./tmp', help='directory for temporary files')
    parser.add_argument('--config', type=str, default='run_tests.config', help='configuration parameters')

    args = parser.parse_args()
    input_file = args.input
    tmp_dir = args.tmp
    output_file = args.output

    with open(args.config, 'r') as f:
        cfg = json.load(f)
        parser_cmd = cfg['parser_cmd']
        extractor_cmd = cfg['extractor_cmd']

    nb_errors = 0
    with io.open(output_file, 'w', encoding='utf-8') as wrt, open(input_file, 'r') as f:
        data = yaml.safe_load(f)
        for itest, test_data in enumerate(data['tests'], start=1):
            if 'test' in test_data:
                data = test_data['test']
                text = data['text']
                print('{}\t{}'.format(itest, text))
                parsing_path = parse(text, parser_cmd, tmp_dir)
                facts_data = extract_facts(parsing_path, extractor_cmd, tmp_dir)
                facts_data = facts_data[0]
                extracted_facts = [ExtractedFact.load_json(fact_data) for fact_data in facts_data['facts']]

                for fact_data in data['facts']:
                    fact_name = fact_data['fact']['fact_name']

                    extracted_fact = None
                    for f in extracted_facts:
                        if f.fact_name == fact_name:
                            extracted_fact = f
                            break

                    if extracted_fact is None:
                        print('Из "{}" не извлечен факт "{}"'.format(text, fact_name))
                        wrt.write('\nТест #{}: из "{}" не извлечен факт "{}"\n'.format(itest, text, fact_name))
                        wrt.flush()
                        nb_errors += 1
                        continue

                    expected_slots = dict()
                    for slot_name in fact_data['fact'].keys():
                        if slot_name != 'fact_name':
                            slot_value = fact_data['fact'][slot_name]
                            expected_slots[slot_name] = slot_value

                    if len(expected_slots) != len(extracted_fact.slots):
                        print('Ошибка при проверке факта "{}", извлеченного из "{}"'.format(fact_name, text))
                        print('Ожидалось {} слотов, извлечено {} слотов'.format(len(expected_slots), len(extracted_fact.slots)))

                        wrt.write('\nТест #{}: ошибка при проверке факта "{}", извлеченного из "{}"\n'.format(itest, fact_name, text))
                        wrt.write('Ожидалось {} слотов, извлечено {} слотов\n'.format(len(expected_slots), len(extracted_fact.slots)))

                        wrt.flush()
                        nb_errors += 1
                        continue

                    for slot_name, slot_value in expected_slots.items():
                        if slot_name not in extracted_fact.slots:
                            print('Ошибка при проверке факта "{}", извлеченного из "{}"'.format(fact_name, text))
                            print('Отсутствует требуемый слот "{}"'.format(slot_name))

                            wrt.write('\nТест #{}: ошибка при проверке факта "{}", извлеченного из "{}"\n'.format(itest, fact_name, text))
                            print('Отсутствует требуемый слот "{}"\n'.format(slot_name))

                            wrt.flush()
                            nb_errors += 1
                        elif extracted_fact.slots[slot_name] != slot_value:
                            print('\nТест #{}: ошибка при проверке факта "{}", извлеченного из "{}"'.format(itest, fact_name, text))
                            print('Для слота "{}" требуется значение "{}", но извлечено "{}"'.format(slot_name, slot_value, extracted_fact.slots[slot_name]))
                            wrt.flush()
                            nb_errors += 1

    if nb_errors == 0:
        print('Тесты успешно закончены, ошибок нет')
    else:
        print('Тесты закончены, всего ошибок: {}'.format(nb_errors))


