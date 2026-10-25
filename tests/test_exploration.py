"""Rendered alternative worlds must precede retained-direction development."""
import tempfile
import json
import hashlib
import os
import subprocess
import sys
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest
from proposition_runtime import state, preservation
from proposition_runtime.experience import inspect_experience
from experience_fixture import prepare_experience, prepare_inputs, write_artifact


class ExplorationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs')
        self.root=Path(self.run['root'])
        self.retained=prepare_experience(self.run,exploration=False,candidate_ids=['a'])

    def check(self):
        return inspect_experience(state.load_run(self.root))

    def mutate(self,identifier,change):
        path=self.root/(identifier+'.json');data=json.loads(path.read_text());change(data)
        write_artifact(self.run,identifier,path.name,data)
        if identifier=='creative-exploration':
            plan=json.loads((self.root/'creative-experience.json').read_text())
            write_artifact(self.run,'creative-experience','creative-experience.json',plan)

    def valid_exploration(self):
        self.retained=prepare_experience(self.run)
        self.assertEqual(self.check()['status'],'PASS',self.check())

    def test_single_retained_world_cannot_count_its_scroll_states_as_exploration(self):
        result=inspect_experience(state.load_run(self.root))
        self.assertEqual(result['status'],'BLOCKED',result)

    def test_freeze_rejects_missing_exploration_before_writing_a_lock(self):
        with self.assertRaises(ValueError):
            preservation.freeze_creatives(self.root,{'revision':'r1','actor':'fixture operator',
                'decision':'Retain the only authored world.','retained':self.retained})
        self.assertFalse((self.root/preservation.LOCK).exists())

    def test_two_compared_worlds_can_develop_and_freeze_only_the_selected_world(self):
        self.valid_exploration()
        self.assertEqual(self.check()['status'],'PASS',self.check())
        preservation.freeze_creatives(self.root,{'revision':'r1','actor':'fixture operator',
            'decision':'Select after comparing the two worlds.','retained':self.retained})
        self.assertEqual(self.check()['status'],'PASS',self.check())

    def test_creative_packet_can_be_prepared_before_candidate_renders(self):
        from proposition_runtime.experience import require_packet_methods
        prepare_inputs(self.run)
        inputs=json.loads((self.root/'creative-inputs.json').read_text())
        require_packet_methods(state.load_run(self.root),['creative-inputs']+[m['reference_ref'].split(':')[1] for m in inputs['methods']])

    def test_scroll_states_of_one_world_cannot_satisfy_a_self_written_mandate(self):
        self.mutate('creative-inputs',lambda d:d.update(creative_mandate={'mode':'external_selection','actor':'author','reason':'Only one world is needed'}))
        inputs=state.load_run(self.root)['artifacts']['creative-inputs']['sha256']
        self.mutate('creative-experience',lambda d:d.update(inputs_sha256=inputs))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_missing_duplicate_stale_or_uninspected_candidate_evidence_blocks(self):
        for defect in ('missing_candidate','duplicate_id','same_render','same_pixels','stale_hash','missing_hash','missing_anchor','same_structure','missing_inspection'):
            with self.subTest(defect=defect):
                self.valid_exploration()
                def damage(data):
                    a,b=data['candidates']
                    if defect=='missing_candidate':data['candidates'].pop()
                    elif defect=='duplicate_id':b['id']=a['id']
                    elif defect in ('same_render','same_pixels'):
                        if defect=='same_pixels':
                            (self.root/'same.png').write_bytes((self.root/'scene.png').read_bytes())
                            row=state.add_artifact(self.root,'same','same.png','public')
                            b.update(central_scene_ref='artifact:same',central_scene_sha256=row['sha256'])
                        else:b.update(central_scene_ref=a['central_scene_ref'],central_scene_sha256=a['central_scene_sha256'])
                    elif defect=='stale_hash':b['central_scene_sha256']='0'*64
                    elif defect=='missing_hash':b.pop('central_scene_sha256')
                    elif defect=='missing_anchor':b['client_anchor']='artifact:creative-inputs'
                    elif defect=='same_structure':b['structure']=a['structure']
                    elif defect=='missing_inspection':b.pop('inspection')
                self.mutate('creative-exploration',damage)
                self.assertEqual(self.check()['status'],'BLOCKED',self.check())

    def test_comparison_and_selection_cannot_postdate_developed_scene_registration(self):
        self.valid_exploration()
        future=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()
        self.mutate('creative-exploration',lambda d:(d['comparison'].update(compared_at=future),d['selection'].update(selected_at=future)))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_selection_cannot_precede_comparison_or_omit_a_candidate(self):
        for defect in ('before_comparison','omitted_candidate','unselected_plan','wrong_inputs'):
            with self.subTest(defect=defect):
                self.valid_exploration()
                def damage(data):
                    if defect=='before_comparison':data['selection']['selected_at']=state.load_run(self.root)['created_at']
                    elif defect=='omitted_candidate':data['comparison']['candidate_ids']=['a']
                    elif defect=='unselected_plan':data['selection']['selected_candidate_ids']=['b']
                    elif defect=='wrong_inputs':data['inputs_sha256']='0'*64
                self.mutate('creative-exploration',damage)
                self.assertEqual(self.check()['status'],'BLOCKED',self.check())

    def test_freeze_cannot_drop_a_developed_beat_before_writing_the_lock(self):
        self.valid_exploration()
        with self.assertRaises(ValueError):
            preservation.freeze_creatives(self.root,{'revision':'r1','actor':'fixture operator',
                'decision':'Drop an arrival scene.','retained':self.retained[:-1]})
        self.assertFalse((self.root/preservation.LOCK).exists())

    def test_selected_world_central_scene_must_reach_its_developed_direction(self):
        self.valid_exploration()
        from creative_fixture import make_scene
        make_scene(self.root,'replacement.png','red')
        state.add_artifact(self.root,'replacement','replacement.png','public')
        self.mutate('creative-experience',lambda d:d['directions'][0]['moments'][0].update(render_ref='artifact:replacement'))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_historical_single_world_remains_readable_without_an_exploration_retrofit(self):
        # Model bytes written by the previous runtime, not a supported new-run opt-out.
        path=self.root/'state.json';run=json.loads(path.read_text())
        run['metadata'].pop('creative_exploration_contract');path.write_text(json.dumps(run))
        self.assertEqual(self.check()['status'],'PASS')

    def test_keep_open_mandate_cannot_be_silently_reduced_to_the_preferred_candidate(self):
        mandate=self.mandate(mode='exact_count',candidate_count=2,selection_policy='keep_open');mandate.pop('candidate_ids')
        run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',creative_mandate=mandate)
        prepare_experience(run)
        result=inspect_experience(state.load_run(run['root']))
        self.assertEqual(result['status'],'BLOCKED')
        self.assertIn('keeping every named direction',result['issues'][0])

    def test_changed_initial_instruction_capture_blocks_the_exception(self):
        run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',creative_mandate=self.mandate())
        prepare_experience(run,candidate_ids=['a'])
        (Path(run['root'])/'creative-mandate-input.txt').write_text('An unrelated instruction')
        self.assertEqual(inspect_experience(state.load_run(run['root']))['status'],'BLOCKED')

    def test_instruction_capture_cannot_block_initialization_on_a_fifo(self):
        mandate=self.mandate();capture=Path(mandate['authority']['input_path'])
        capture.unlink();os.mkfifo(capture)
        manifest=(Path(self.tmp.name)/'fifo-mandate.json').resolve();manifest.write_text(json.dumps(mandate))
        launcher=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        try:
            result=subprocess.run([sys.executable,str(launcher),'init','https://fixture.example/',
                '--runs-root',str(Path(self.tmp.name)/'fifo-runs'),'--creative-mandate',str(manifest)],
                capture_output=True,text=True,timeout=2)
        except subprocess.TimeoutExpired:
            self.fail('An instruction FIFO blocked initialization instead of being rejected')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(json.loads(result.stdout)['status'],'ERROR')
        self.assertFalse((Path(self.tmp.name)/'fifo-runs').exists())

    def test_instruction_capture_larger_than_256_kib_cannot_initialize_a_mandate(self):
        mandate=self.mandate();capture=Path(mandate['authority']['input_path'])
        content=capture.read_bytes().ljust(256*1024+1,b' ');capture.write_bytes(content)
        mandate['authority']['input_sha256']=hashlib.sha256(content).hexdigest()
        with self.assertRaises(ValueError):
            state.init_run('https://fixture.example/',Path(self.tmp.name)/'oversize-runs',creative_mandate=mandate)
        self.assertFalse((Path(self.tmp.name)/'oversize-runs').exists())

    def test_instruction_capture_at_256_kib_can_initialize_a_mandate(self):
        mandate=self.mandate();capture=Path(mandate['authority']['input_path'])
        content=capture.read_bytes().ljust(256*1024,b' ');capture.write_bytes(content)
        mandate['authority']['input_sha256']=hashlib.sha256(content).hexdigest()
        run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'boundary-runs',creative_mandate=mandate)
        from proposition_runtime.experience import exploration_contract
        self.assertEqual(exploration_contract(run)['mode'],'external_selection')

    def test_stalled_ordinary_instruction_read_has_a_five_second_deadline(self):
        from proposition_runtime import experience
        mandate=self.mandate();capture=Path(mandate['authority']['input_path'])
        worker=(Path(self.tmp.name)/'stalled-reader').resolve()
        worker.write_text('#!'+sys.executable+'\nimport sys,time\nfrom pathlib import Path\ntime.sleep(7)\nsys.stdout.buffer.write(Path(sys.argv[-2]).read_bytes())\n')
        worker.chmod(0o700)
        # Real child execution deliberately stalls an otherwise ordinary file read.
        with patch.object(experience,'sys',sys,create=True),patch.object(sys,'executable',str(worker)):
            with self.assertRaisesRegex(ValueError,'deadline'):
                experience.read_mandate_input(capture)

    def test_authority_replaced_with_a_fifo_or_symlink_blocks_the_existing_run(self):
        for replacement in ('fifo','symlink'):
            with self.subTest(replacement=replacement):
                run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',creative_mandate=self.mandate())
                prepare_experience(run,candidate_ids=['a'])
                capture=Path(run['root'])/'creative-mandate-input.txt';capture.unlink()
                if replacement=='fifo':os.mkfifo(capture)
                else:capture.symlink_to(Path(self.tmp.name)/'current-user-input.txt')
                launcher=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
                try:
                    result=subprocess.run([sys.executable,str(launcher),'check-experience',run['root']],
                        capture_output=True,text=True,timeout=2)
                except subprocess.TimeoutExpired:
                    self.fail('A replaced authority capture blocked its run gate')
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(json.loads(result.stdout)['status'],'BLOCKED')

    def test_initialized_contract_cannot_be_removed_or_downgraded(self):
        for change in ('remove','downgrade'):
            run=state.load_run(self.root)
            if change=='remove':run.get('metadata',{}).pop('creative_exploration_contract',None)
            else:run.setdefault('metadata',{})['creative_exploration_contract']={'version':0,'mode':'external_selection'}
            with self.subTest(change=change),self.assertRaises(ValueError):state.save_run(self.root,run)

    def test_profile_and_authored_inputs_cannot_override_the_default_count(self):
        run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',
            {'parameters':{'creative_exploration_contract':{'version':0},'creative_mandate':{'mode':'exact_count','candidate_count':1}}})
        prepare_experience(run,candidate_ids=['a'])
        self.assertEqual(inspect_experience(state.load_run(run['root']))['status'],'BLOCKED')

    def mandate(self,**changes):
        text=('Explore exactly '+str(changes.get('candidate_count',1))+' candidate worlds.'
              if changes.get('mode')=='exact_count' else
              'The client has already chosen direction a. Continue that direction only.')
        if changes.get('selection_policy')=='keep_open':text+=' Keep every candidate direction open.'
        path=(Path(self.tmp.name)/'current-user-input.txt').resolve();path.write_text(text)
        data={'version':1,'mode':'external_selection','candidate_count':1,'candidate_ids':['a'],
            'authority':{'kind':'current_user_instruction','input_path':str(path),'input_sha256':hashlib.sha256(text.encode()).hexdigest(),
                'quote':text,'captured_at':datetime.now(timezone.utc).isoformat(),'site_url':'https://fixture.example/'}}
        data.update(changes);return data

    def test_explicit_initialized_chosen_direction_can_continue_without_fake_alternatives(self):
        run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',creative_mandate=self.mandate())
        prepare_experience(run,candidate_ids=['a'])
        self.assertEqual(inspect_experience(state.load_run(run['root']))['status'],'PASS')

    def test_explicit_exact_count_of_one_is_respected(self):
        mandate=self.mandate(mode='exact_count');mandate.pop('candidate_ids')
        run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',creative_mandate=mandate)
        prepare_experience(run,candidate_ids=['a'])
        self.assertEqual(inspect_experience(state.load_run(run['root']))['status'],'PASS')

    def test_initialized_exact_count_cannot_be_silently_reduced(self):
        mandate=self.mandate(mode='exact_count',candidate_count=2);mandate.pop('candidate_ids')
        run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',creative_mandate=mandate)
        prepare_experience(run,candidate_ids=['a'])
        self.assertEqual(inspect_experience(state.load_run(run['root']))['status'],'BLOCKED')

    def test_missing_stale_website_or_mismatched_instruction_authority_cannot_initialize_an_exception(self):
        for defect in ('missing_authority','site_source','wrong_site','wrong_hash','wrong_quote','stale','actor_only','downgrade'):
            with self.subTest(defect=defect):
                mandate=self.mandate()
                if defect=='missing_authority':mandate.pop('authority')
                elif defect=='actor_only':mandate['authority']={'actor':'operator','reason':'Client chose this'}
                elif defect=='site_source':mandate['authority']['kind']='website_quote'
                elif defect=='wrong_site':mandate['authority']['site_url']='https://other.example/'
                elif defect=='wrong_hash':mandate['authority']['input_sha256']='0'*64
                elif defect=='wrong_quote':mandate['authority']['quote']='Different instruction'
                elif defect=='stale':mandate['authority']['captured_at']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
                elif defect=='downgrade':mandate['version']=0
                with self.assertRaises(ValueError):state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',creative_mandate=mandate)
