import os
import numpy as np
import pandas as pd
import torch
from matplotlib import pyplot as plt

from evaluate_params import eval_func_param_names, eval_extra_columns, input_args_list
from gen import evaluate, check_locals, score_qa
from prompter import Prompter
from utils import clear_torch_cache, NullContext, get_kwargs, makedirs


def run_eval(  # for local function:
        base_model=None, lora_weights=None, inference_server=None, regenerate_clients=None, regenerate_gradio_clients=None,
        prompt_type=None, prompt_dict=None, system_prompt=None,
        debug=None, chat=False,
        stream_output=None, async_output=None, num_async=None, stream_map=None,
        eval_filename=None, eval_prompts_only_num=None, eval_prompts_only_seed=None, eval_as_output=None,
        examples=None, memory_restriction_level=None,
        # evaluate kwargs
        n_jobs=None, llamacpp_path=None, llamacpp_dict=None, exllama_dict=None, gptq_dict=None, attention_sinks=None,
        sink_dict=None, truncation_generation=None,
        hf_model_dict=None,
        force_seq2seq_type=None, force_t5_type=None,
        load_exllama=None,

        use_pymupdf=None,
        use_unstructured_pdf=None,
        use_pypdf=None,
        enable_pdf_ocr=None,
        enable_pdf_doctr=None,
        enable_image=None,
        visible_image_models=None,

        try_pdf_as_html=None,
        # for evaluate args beyond what's already above, or things that are always dynamic and locally created
        load_awq='',
        temperature=None,
        top_p=None,
        top_k=None,
        penalty_alpha=None,
        num_beams=None,
        max_new_tokens=None,
        min_new_tokens=None,
        early_stopping=None,
        max_time=None,
        repetition_penalty=None,
        num_return_sequences=None,
        do_sample=None,
        seed=None,
        langchain_mode=None,
        langchain_action=None,
        langchain_agents=[],
        top_k_docs=None,
        chunk=None,
        chunk_size=None,
        document_subset=None,
        document_choice=None,
        document_source_substrings=None,
        document_source_substrings_op=None,
        document_content_substrings=None,
        document_content_substrings_op=None,
        pre_prompt_query=None, prompt_query=None,
        pre_prompt_summary=None, prompt_summary=None, hyde_llm_prompt=None,

        user_prompt_for_fake_system_prompt=None,
        json_object_prompt=None,
        json_object_prompt_simpler=None,
        json_code_prompt=None,
        json_schema_instruction=None,

        image_audio_loaders=None,
        pdf_loaders=None,
        url_loaders=None,
        jq_schema=None,
        extract_frames=None,
        extract_frames0=None,
        llava_prompt=None,
        visible_models=None,
        h2ogpt_key=None,
        add_search_to_context=None,
        chat_conversation=None,
        text_context_list=None,
        docs_ordering_type=None,
        min_max_new_tokens=None,
        max_input_tokens=None,
        max_total_input_tokens=None,
        docs_token_handling=None,
        docs_joiner=None,
        hyde_level=None,
        hyde_template=None,
        hyde_show_only_final=None,
        hyde_show_intermediate_in_accordion=None,
        map_reduce_show_intermediate_in_accordion=None,
        doc_json_mode=None,
        metadata_in_context=None,
        chatbot_role=None,
        speaker=None,
        tts_language=None,
        tts_speed=None,
        image_file=None,
        image_control=None,

        response_format=None,
        guided_json=None,
        guided_regex=None,
        guided_choice=None,
        guided_grammar=None,

        # for evaluate kwargs:
        captions_model=None,
        caption_loader=None,
        doctr_loader=None,
        pix2struct_loader=None,
        llava_model=None,
        image_model_dict=None,

        asr_model=None,
        asr_loader=None,

        image_audio_loaders_options0=None,
        pdf_loaders_options0=None,
        url_loaders_options0=None,
        jq_schema0=None,
        keep_sources_in_context=None,
        gradio_errors_to_chatbot=None,
        allow_chat_system_prompt=None,
        src_lang=None, tgt_lang=None, concurrency_count=None, save_dir=None, sanitize_bot_response=None,
        model_state0=None,
        use_auth_token=None,
        trust_remote_code=None,
        score_model_state0=None,
        max_max_new_tokens=None,
        is_public=None,
        max_max_time=None,
        raise_generate_gpu_exceptions=None, load_db_if_exists=None, use_llm_if_no_docs=None,
        my_db_state0=None, selection_docs_state0=None, dbs=None, langchain_modes=None, langchain_mode_paths=None,
        detect_user_path_changes_every_query=None,
        use_openai_embedding=None, use_openai_model=None,
        hf_embedding_model=None, migrate_embedding_model=None,
        cut_distance=None,
        answer_with_sources=None,
        append_sources_to_answer=None,
        append_sources_to_chat=None,
        sources_show_text_in_accordion=None,
        top_k_docs_max_show=None,
        show_link_in_sources=None,
        langchain_instruct_mode=None,
        add_chat_history_to_context=None,
        context=None, iinput=None,
        db_type=None, first_para=None, text_limit=None, verbose=None,
        gradio=None, cli=None,
        use_cache=None,
        auto_reduce_chunks=None, max_chunks=None, headsize=None,
        model_lock=None, force_langchain_evaluate=None,
        model_state_none=None,
):
    from_ui = False
    # makes no sense to evaluate document content for langchain case
    answer_with_sources = False
    show_link_in_sources = False
    append_sources_to_answer = False
    append_sources_to_chat = False

    check_locals(**locals().copy())

    if not context:
        context = ''

    if eval_prompts_only_num > 0:
        np.random.seed(eval_prompts_only_seed)
        example1 = examples[-1]  # pick reference example
        examples = []
        responses = []
        if eval_filename is None:
            # override default examples with shareGPT ones for human-level eval purposes only
            eval_filename = 'ShareGPT_V3_unfiltered_cleaned_split_no_imsorry.json'
            if not os.path.isfile(eval_filename):
                os.system(
                    'wget https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered/resolve/main/%s' % eval_filename)
            import json
            with open(eval_filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # focus on data that starts with human, else likely chopped from other data
            turn_start = 0  # odd in general
            data = [x for x in data if len(x['conversations']) > turn_start + 1 and
                    x['conversations'][turn_start]['from'] == 'human' and
                    x['conversations'][turn_start + 1]['from'] == 'gpt']
            for i in sorted(np.random.randint(0, len(data), size=eval_prompts_only_num)):
                assert data[i]['conversations'][turn_start]['from'] == 'human'
                instruction = data[i]['conversations'][turn_start]['value']
                assert data[i]['conversations'][turn_start + 1]['from'] == 'gpt'
                output = data[i]['conversations'][turn_start + 1]['value']
                examplenew = example1.copy()
                assert not chat, "No gradio must use chat=False, uses nochat instruct"
                examplenew[eval_func_param_names.index('instruction_nochat')] = instruction
                examplenew[eval_func_param_names.index('iinput_nochat')] = iinput
                examplenew[eval_func_param_names.index('context')] = context
                examples.append(examplenew)
                responses.append(output)
        else:
            # get data, assume in correct format: json of rows of dict of instruction and output
            # only instruction is required
            import json
            with open(eval_filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for i in sorted(np.random.randint(0, len(data), size=eval_prompts_only_num)):
                examplenew = example1.copy()
                instruction = data[i]['instruction']
                output = data[i].get('output', '')  # not required
                assert not chat, "No gradio must use chat=False, uses nochat instruct"
                examplenew[eval_func_param_names.index('instruction_nochat')] = instruction
                examplenew[eval_func_param_names.index('iinput_nochat')] = iinput
                examplenew[eval_func_param_names.index('context')] = context
                examples.append(examplenew)
                responses.append(output)

    num_examples = len(examples)
    scoring_path = 'scoring'
    # if no permissions, assume may not want files, put into temp
    scoring_path = makedirs(scoring_path, tmp_ok=True, use_base=True)
    if eval_as_output:
        used_base_model = 'gpt35'
        used_lora_weights = ''
        used_inference_server = ''
    else:
        used_base_model = str(base_model.split('/')[-1])
        used_lora_weights = str(lora_weights.split('/')[-1])
        used_inference_server = str(inference_server.split('/')[-1])
    eval_out_filename = "df_scores_%s_%s_%s_%s_%s_%s_%s.parquet" % (num_examples, eval_prompts_only_num,
                                                                    eval_prompts_only_seed,
                                                                    eval_as_output,
                                                                    used_base_model,
                                                                    used_lora_weights,
                                                                    used_inference_server,
                                                                    )
    eval_out_filename = os.path.join(scoring_path, eval_out_filename)

    smodel = score_model_state0['model']
    stokenizer = score_model_state0['tokenizer']
    sdevice = score_model_state0['device']

    # torch.device("cuda") leads to cuda:x cuda:y mismatches for multi-GPU consistently
    n_gpus = torch.cuda.device_count() if torch.cuda.is_available() else 0
    device = 'cpu' if n_gpus == 0 else 'cuda'
    context_class = NullContext if n_gpus > 1 or n_gpus == 0 else torch.device

    with context_class(device):
        # ensure was set right above before examples generated
        assert not stream_output, "stream_output=True does not make sense with example loop"
        import time
        from functools import partial

        if not eval_as_output:
            requests_state0 = {}
            roles_state0 = None
            args = (None, my_db_state0, selection_docs_state0, requests_state0, roles_state0)
            assert len(args) == len(input_args_list)
            fun = partial(evaluate,
                          *args,
                          **get_kwargs(evaluate, exclude_names=input_args_list + eval_func_param_names,
                                       **locals().copy()))
        else:
            assert eval_prompts_only_num > 0

            def get_response(*args, exi=0):
                # assumes same ordering of examples and responses
                yield responses[exi]

            fun = get_response
        t0 = time.time()
        score_dump = []
        score_avg = 0
        score_median = 0

        for exi, ex in enumerate(examples):
            clear_torch_cache(allow_skip=True)

            instruction = ex[eval_func_param_names.index('instruction_nochat')]
            iinput = ex[eval_func_param_names.index('iinput_nochat')]
            context = ex[eval_func_param_names.index('context')]
            clear_torch_cache(allow_skip=True)
            print("")
            print("START" + "=" * 100)
            print("Question: %s %s" % (instruction, ('input=%s' % iinput if iinput else '')))
            print("-" * 105)
            # fun yields as generator, so have to iterate over it
            # Also means likely do NOT want --stream_output=True, else would show all generations
            t1 = time.time()

            # grab other parameters, like langchain_mode
            eval_vars = ex.copy()
            for k in eval_func_param_names:
                if k in locals().copy():
                    eval_vars[eval_func_param_names.index(k)] = locals().copy()[k]

            gener = fun(*tuple(eval_vars), exi=exi) if eval_as_output else fun(*tuple(eval_vars))
            for res_fun in gener:
                res = res_fun['response']
                sources = res_fun.get('sources', 'Failure of Generation')
                print(res)
                if smodel:
                    score_with_prompt = False
                    if score_with_prompt:
                        data_point = dict(instruction=instruction, input=iinput, context=context)
                        prompter = Prompter(prompt_type, prompt_dict,
                                            debug=debug, stream_output=stream_output)
                        prompt = prompter.generate_prompt(data_point, context_from_history=False)
                    else:
                        # just raw input and output
                        if eval_prompts_only_num > 0:
                            # only our own examples have this filled at moment
                            assert iinput in [None, ''], iinput  # should be no iinput
                        prompt = instruction
                    score = score_qa(smodel, stokenizer, prompt, res, memory_restriction_level=memory_restriction_level)
                    score_dump.append(ex + [prompt, res, score])
                    # dump every score in case abort
                    df_scores = pd.DataFrame(score_dump,
                                             columns=eval_func_param_names +
                                                     eval_extra_columns)
                    df_scores.to_parquet(eval_out_filename, index=False)
                    if not isinstance(score, str):
                        # plot histogram so far
                        plt.figure(figsize=(10, 10))
                        plt.hist(df_scores['score'], bins=20)
                        score_avg = np.mean(df_scores['score'])
                        score_median = np.median(df_scores['score'])
                        print("SCORE %s: %s  So far: AVG: %s MEDIAN: %s" % (exi, score, score_avg, score_median),
                              flush=True)
                        plt.title("Score avg: %s median: %s" % (score_avg, score_median))
                        plt.savefig(eval_out_filename.replace('.parquet', '.png'))
                        plt.close()

            print("END" + "=" * 102)
            print("")
            t2 = time.time()
            print("Time taken for example: %s Time taken so far: %.4f about %.4g per example" % (
                t2 - t1, t2 - t0, (t2 - t0) / (1 + exi)))
        t1 = time.time()
        print("Total time taken: %.4f about %.4g per example" % (t1 - t0, (t1 - t0) / num_examples))
        print("Score avg: %s median: %s" % (score_avg, score_median), flush=True)
    return eval_out_filename
